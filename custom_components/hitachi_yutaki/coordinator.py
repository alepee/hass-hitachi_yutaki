"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .adapters.clock import HomeAssistantClock
from .adapters.derived_metrics import DerivedMetricsAdapter
from .api import HitachiApiClient
from .api.base import ReadResult
from .const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_MODES,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    CONF_CYCLING_DETECTION,
    CONF_EXTERNAL_ROOM_SENSOR_NOTICE,
    CONF_REFRIGERANT_DETECTION,
    DEFAULT_CYCLING_DETECTION,
    DEFAULT_REFRIGERANT_DETECTION,
    DOMAIN,
    RESET_SOURCE_BUTTON,
    RESET_SOURCE_SERVICED,
)
from .domain.services.cycling import (
    PERIOD_THRESHOLD_MIN as CYCLING_PERIOD_THRESHOLD_MIN,
)
from .domain.services.defrost_guard import DefrostGuard
from .domain.services.maintenance import (
    cycling_alert_policy,
    refrigerant_alert_policy,
)
from .profiles import HitachiHeatPumpProfile
from .telemetry import (
    FleetPingUnit,
    HttpTelemetryClient,
    InstallationInfo,
    MetricsBatch,
    NoopTelemetryClient,
    RegisterSnapshot,
    SendResult,
    TelemetryCollector,
)
from .telemetry.anonymizer import (
    anonymize_installation_info,
    anonymize_point,
)

_LOGGER = logging.getLogger(__name__)

_CYCLING_DOC_URL = (
    "https://github.com/alepee/hass-hitachi_yutaki/blob/main/"
    "docs/reference/cycling-monitoring.md"
)

_MAX_BACKOFF = timedelta(seconds=300)

# How often a healthy entry re-checks that the client still reads its unit
# (#476). Also checked on the first poll after any failure, which is when a
# gateway reboot would have moved the units.
_UNIT_CHECK_INTERVAL = 60.0

KEPT_VALUES_STORE_VERSION = 1
_KEPT_VALUES_SAVE_DELAY_S = 10


class HitachiYutakiDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Hitachi heat pump data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: HitachiApiClient,
        profile: HitachiHeatPumpProfile,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.profile = profile
        self.entities: list[Any] = []
        self._defrost_guard = DefrostGuard(clock=HomeAssistantClock(hass))

        # Derived metrics adapter (injected by async_setup_entry)
        self.derived_metrics: DerivedMetricsAdapter | None = None
        self._normal_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
        self._gateway_not_ready_count: int = 0
        # Monotonic time of the last unit slot check, None to check next poll.
        self._unit_checked_at: float | None = None
        # Seed from persisted value (0 = unknown / never refreshed) so callers
        # of has_dhw/has_pool/has_circuit get sensible answers before the
        # first successful refresh. The api_client cache is the live source,
        # this attribute only mirrors what's been observed for diagnostics.
        self.system_config: int = entry.data.get("system_config", 0)
        # Alarm the unit currently reports, and when this poll loop first saw it.
        self._alarm_code: str | None = None
        self._alarm_since: datetime | None = None

        # References of the values the gateway writes back after a reboot
        # (#511), loaded before the first poll.
        self._kept_values_store: Store | None = None

        # Telemetry (injected by async_setup_entry — always set, noop when OFF)
        self.telemetry_collector: TelemetryCollector = None  # type: ignore[assignment]
        self.telemetry_client: HttpTelemetryClient | NoopTelemetryClient = None  # type: ignore[assignment]
        self._telemetry_meta: dict[str, Any] = {}
        self._installation_info_sent: bool = False
        self._installation_sent_date: date | None = None
        self._snapshot_sent: bool = False
        self._onetime_send_lock: asyncio.Lock = asyncio.Lock()
        self._telemetry_next_retry: datetime | None = None
        self._telemetry_retry_delay: int = 30  # seconds, doubles on each failure
        self.telemetry_last_send: datetime | None = None
        self.telemetry_send_failures: int = 0

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )

    @property
    def defrost_guard(self) -> DefrostGuard:
        """Return the defrost guard (owned by derived_metrics adapter when available)."""
        if self.derived_metrics is not None:
            return self.derived_metrics.defrost_guard
        return self._defrost_guard

    @property
    def refrigerant_detection_active(self) -> bool:
        """True only when the profile exposes extended sensors AND the user opted in."""
        return bool(
            self.profile.supports_extended_compressor_sensors
            and self.config_entry.options.get(
                CONF_REFRIGERANT_DETECTION, DEFAULT_REFRIGERANT_DETECTION
            )
        )

    @property
    def cycling_detection_active(self) -> bool:
        """True when the user opted in to short-cycling detection.

        Unlike the refrigerant detector there is no capability gate: every
        profile has a compressor, and the signal (running or not) is universal.
        """
        return bool(
            self.config_entry.options.get(
                CONF_CYCLING_DETECTION, DEFAULT_CYCLING_DETECTION
            )
        )

    @property
    def gateway_not_ready(self) -> bool:
        """Return True when the most recent poll hit GATEWAY_NOT_READY.

        Set by ``_async_update_data`` and cleared on the first successful read.
        Used by setup code to discriminate a transient H-LINK init window from
        a genuine connectivity failure.
        """
        return self._gateway_not_ready_count > 0

    async def _async_verify_unit(self) -> None:
        """Reload the entry when the client no longer reads its unit (#476).

        On a gateway hosting several units, a gateway reboot while Home
        Assistant runs can move a unit to another address; polling would then
        carry on reading another unit's data under this entry's name. Checked
        on the first good poll after any failure (when such a reboot shows up)
        and periodically otherwise. Raises ``UpdateFailed`` and schedules a
        reload, which binds the client to the unit again.
        """
        now = time.monotonic()
        if (
            self._unit_checked_at is not None
            and now - self._unit_checked_at < _UNIT_CHECK_INTERVAL
        ):
            return
        verified = await self.api_client.async_verify_unit()
        if verified is None:
            return
        self._unit_checked_at = now
        if verified:
            return

        self._unit_checked_at = None
        self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        raise UpdateFailed("Heat pump unit moved to another gateway address")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hitachi Yutaki."""
        try:
            if not self.api_client.connected:
                await self.api_client.connect()

            # Build full list of keys and fetch all data
            keys_to_read = self.api_client.base_keys + self.profile.extra_register_keys

            _LOGGER.debug("Reading %d keys from gateway", len(keys_to_read))
            result = await self.api_client.read_values(keys_to_read)

            if result == ReadResult.GATEWAY_NOT_READY:
                self._unit_checked_at = None
                self._gateway_not_ready_count += 1
                backoff = min(
                    self._normal_interval * (2**self._gateway_not_ready_count),
                    _MAX_BACKOFF,
                )
                self.update_interval = backoff
                raise UpdateFailed(
                    "Gateway is not ready (initializing or desynchronized)"
                )

            # Same unit as before, or nothing below may be written to it.
            await self._async_verify_unit()

            # Write back what a gateway or controller reboot cleared (#511),
            # before the values are published.
            await self.api_client.restore_lost_values()

            # Gateway is ready - restore normal interval if needed
            if self._gateway_not_ready_count > 0:
                _LOGGER.info(
                    "Gateway recovered, restoring normal polling interval (%ss).",
                    self._normal_interval.total_seconds(),
                )
                self._gateway_not_ready_count = 0
                self.update_interval = self._normal_interval

            data: dict[str, Any] = {"is_available": True}

            # Populate data from the client
            for key in keys_to_read:
                data[key] = await self.api_client.read_value(key)

            self.system_config = data.get("system_config", 0)

            # Poll succeeded: clear any connection error issue now, before
            # the post-fetch stages, so an enrichment bug cannot keep it
            # alive or re-create it.
            ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

        except UpdateFailed:
            # Re-raise so the generic Exception handler below doesn't
            # turn our intentional UpdateFailed into an HA issue.
            raise

        except Exception as exc:
            self._unit_checked_at = None
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "connection_error",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="connection_error",
            )
            _LOGGER.warning("Error communicating with Hitachi Yutaki gateway: %s", exc)
            raise UpdateFailed("Failed to communicate with device") from exc

        # Post-fetch stages: bookkeeping and pure computation on registers
        # already fetched. A failure here is a software bug, not a gateway
        # communication error: log it with a stack trace and return the raw
        # poll data so register-backed entities stay fresh (#386).
        try:
            # Persist system_config in entry.data so COP services can be
            # seeded at next setup *before* the first refresh (#308).
            # Only write when the value actually changed to avoid churn.
            persisted = self.config_entry.data.get("system_config")
            if self.system_config and persisted != self.system_config:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        "system_config": self.system_config,
                    },
                )

            self._update_alarm_issue(data.get("alarm_code"))

            # Inject api_client state into data for derived metrics
            data["is_defrosting"] = self.api_client.is_defrosting
            data["is_compressor_running"] = self.api_client.is_compressor_running

            # Enrich data with derived metrics (thermal power, COP, timing)
            if self.derived_metrics is not None:
                self.derived_metrics.update(data)
                self._update_refrigerant_issue()
                self._update_cycling_issue()

            self._update_external_room_sensor_notice()
            self._update_kept_values()

            # Telemetry: collect metrics from this poll cycle
            # (collector handles level=OFF internally)
            self.telemetry_collector.collect(data)

            # Re-arm the daily installation re-send before the send gate so a
            # stable install stays visible in WAE's 90-day fleet window.
            self._maybe_rearm_installation_resend(datetime.now(tz=UTC).date())

            # Send one-time telemetry data (with backoff on failure)
            # Fire-and-forget to avoid blocking the Modbus poll path
            if not self._installation_info_sent or not self._snapshot_sent:
                self.hass.async_create_task(self._send_onetime_telemetry(data))
        except Exception:
            _LOGGER.exception(
                "Post-fetch enrichment failed; returning raw poll data "
                "(this is an integration bug, not a gateway problem)"
            )

        return data

    async def _send_onetime_telemetry(self, data: dict[str, Any]) -> None:
        """Send one-time telemetry (installation info + snapshot) with backoff."""
        if self._onetime_send_lock.locked():
            return

        async with self._onetime_send_lock:
            now = datetime.now(tz=UTC)

            # Respect backoff delay
            if self._telemetry_next_retry and now < self._telemetry_next_retry:
                return

            success = True

            if not self._installation_info_sent:
                await self._send_installation_info()
                if not self._installation_info_sent:
                    success = False

            if not self._snapshot_sent:
                await self._send_register_snapshot(data)
                if not self._snapshot_sent:
                    success = False

            if not success:
                # Exponential backoff: 30s, 60s, 120s, 240s, capped at 5 min
                self._telemetry_next_retry = now + timedelta(
                    seconds=self._telemetry_retry_delay
                )
                self._telemetry_retry_delay = min(self._telemetry_retry_delay * 2, 300)
            else:
                self._telemetry_next_retry = None
                # Reset so each new day's installation re-send starts with a fresh backoff baseline.
                self._telemetry_retry_delay = 30

    def _maybe_rearm_installation_resend(self, today: date) -> None:
        """Re-arm the installation telemetry send when the UTC day changes.

        WAE retains 90 days, so a stable installation that never restarts HA
        would otherwise drop off the fleet dashboard. Re-arming once per UTC
        day keeps the 90-day window populated. The actual send rides the
        existing one-time send path (lock + exponential backoff). Only the
        installation flag is re-armed; the register snapshot is a genuine
        one-time payload and is intentionally left sent.
        """
        if (
            self._installation_sent_date is not None
            and self._installation_sent_date != today
        ):
            self._installation_info_sent = False

    def _unit_capabilities(self) -> dict[str, Any]:
        """Return the unit's capabilities, shared by telemetry and fleet ping."""
        has_cooling = self.has_circuit(
            CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING
        ) or self.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)

        return {
            "has_dhw": self.has_dhw(),
            "has_pool": self.has_pool(),
            "has_cooling": has_cooling,
            "max_circuits": self.profile.max_circuits,
            "has_secondary_compressor": self.profile.supports_secondary_compressor,
        }

    def fleet_ping_unit(self) -> FleetPingUnit | None:
        """Describe this unit for the fleet ping, once a poll has succeeded.

        None before the first successful poll: the capabilities come from the
        gateway's system configuration, unknown until then.
        """
        if not self.last_update_success or not self.data:
            return None
        meta = self._telemetry_meta
        return FleetPingUnit(
            profile=meta["profile"],
            gateway_type=meta["gateway_type"],
            power_supply=meta["power_supply"],
            **self._unit_capabilities(),
        )

    def _issue_dismissed(self, issue_id: str) -> bool:
        """Return True when the user dismissed (ignored) this repair issue."""
        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, issue_id)
        return issue is not None and issue.dismissed_version is not None

    def _maintenance_telemetry(self) -> dict[str, Any]:
        """Describe the preventive-maintenance detectors for the daily payload.

        The verdicts already travel in the metrics points; this adds what the
        points cannot tell: the user's consent (so a missing verdict reads as
        "off" or "unsupported" rather than "unknown"), the baseline resets per
        source, and whether the user ignored the repair issue.
        """
        options = self.config_entry.options
        if not self.profile.supports_extended_compressor_sensors:
            refrigerant = "unsupported"
        elif CONF_REFRIGERANT_DETECTION not in options:
            refrigerant = "undecided"
        else:
            refrigerant = "on" if options[CONF_REFRIGERANT_DETECTION] else "off"
        info: dict[str, Any] = {
            "refrigerant_detection": refrigerant,
            "cycling_detection": "on" if self.cycling_detection_active else "off",
        }
        if self.refrigerant_detection_active and self.derived_metrics is not None:
            resets = self.derived_metrics.refrigerant_resets
            info.update(
                refrigerant_resets_button=resets[RESET_SOURCE_BUTTON],
                refrigerant_resets_serviced=resets[RESET_SOURCE_SERVICED],
                refrigerant_days_since_reset=(
                    self.derived_metrics.refrigerant_days_since_reset
                ),
                refrigerant_issue_dismissed=self._issue_dismissed(
                    self._refrigerant_issue_id()
                ),
            )
        if self.cycling_detection_active:
            info["cycling_issue_dismissed"] = self._issue_dismissed(
                self._cycling_issue_id()
            )
        return info

    async def _send_installation_info(self) -> None:
        """Build and send installation info on first successful poll."""
        meta = self._telemetry_meta

        info = InstallationInfo(
            instance_hash=meta["instance_hash"],
            device_hash=meta["device_hash"],
            profile=meta["profile"],
            gateway_type=meta["gateway_type"],
            ha_version=meta["ha_version"],
            integration_version=meta["integration_version"],
            power_supply=meta["power_supply"],
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            **self._unit_capabilities(),
            **self._maintenance_telemetry(),
        )
        info = anonymize_installation_info(info)

        try:
            success = await self.telemetry_client.send_installation(info)
            if success:
                self._installation_info_sent = True
                self._installation_sent_date = datetime.now(tz=UTC).date()
        except Exception:
            _LOGGER.debug(
                "[%s] Failed to send telemetry installation info",
                self.config_entry.title,
                exc_info=True,
            )

    async def _send_register_snapshot(self, data: dict[str, Any]) -> None:
        """Send a one-time register snapshot."""
        if self._snapshot_sent:
            return

        meta = self._telemetry_meta

        # Build register dict: only numeric values, skip meta keys
        registers: dict[str, float] = {}
        for key, value in data.items():
            if key == "is_available":
                continue
            if isinstance(value, (int, float)):
                registers[key] = value

        snapshot = RegisterSnapshot(
            instance_hash=meta["instance_hash"],
            device_hash=meta["device_hash"],
            time=datetime.now(tz=UTC),
            profile=meta["profile"],
            gateway_type=meta["gateway_type"],
            registers=registers,
        )

        try:
            success = await self.telemetry_client.send_snapshot(snapshot)
            if success:
                self._snapshot_sent = True
                _LOGGER.debug(
                    "[%s] Telemetry: register snapshot sent", self.config_entry.title
                )
        except Exception:
            _LOGGER.debug(
                "[%s] Failed to send register snapshot",
                self.config_entry.title,
                exc_info=True,
            )

    async def async_flush_telemetry(self) -> bool:
        """Flush telemetry buffer and send data.

        Return True when a batch reached the endpoint, so the caller can tell
        a backlog worth draining early from one left by a failing send.
        """
        points = self.telemetry_collector.flush()
        if not points:
            return False

        instance_hash = self._telemetry_meta["instance_hash"]
        device_hash = self._telemetry_meta["device_hash"]

        # Decided in the branches below, acted on once in `finally`. Re-queueing
        # inline would run twice if anything after it raised, and would be
        # skipped entirely on cancellation.
        requeue_needed = False
        delivered = False
        try:
            anonymized = [anonymize_point(p) for p in points]
            batch = MetricsBatch(
                instance_hash=instance_hash, device_hash=device_hash, points=anonymized
            )
            result = await self.telemetry_client.send_metrics(batch)

            if result:
                self.telemetry_last_send = datetime.now(tz=UTC)
                delivered = True
            elif result is SendResult.PROBABLY_DELIVERED:
                # The endpoint rate-limited a retry of an attempt whose answer
                # we never saw, which means that attempt was archived. Keeping
                # the points would write them a second time (#395).
                _LOGGER.info(
                    "[%s] Telemetry flush: batch of %d points already accepted "
                    "by the endpoint, not re-queued",
                    self.config_entry.title,
                    len(points),
                )
            elif result is SendResult.PAYLOAD_TOO_LARGE:
                # The batch itself is unacceptable, so re-queueing it would
                # grow the next one and pin telemetry on a permanent rejection.
                # Drop the points instead (#395).
                self.telemetry_send_failures += 1
                _LOGGER.warning(
                    "[%s] Telemetry flush: batch of %d points rejected as too "
                    "large, dropping it",
                    self.config_entry.title,
                    len(points),
                )
            else:
                self.telemetry_send_failures += 1
                requeue_needed = True
                _LOGGER.warning(
                    "[%s] Telemetry flush: send returned failure",
                    self.config_entry.title,
                )
        except asyncio.CancelledError:
            # Home Assistant shutting down mid-send, typically while the client
            # waits between retries. CancelledError derives from BaseException,
            # so `except Exception` lets the already-flushed points vanish
            # instead of putting them back for the unload flush (#395).
            requeue_needed = True
            raise
        except Exception:
            self.telemetry_send_failures += 1
            requeue_needed = True
            _LOGGER.warning(
                "[%s] Telemetry flush failed",
                self.config_entry.title,
                exc_info=True,
            )
        finally:
            if requeue_needed:
                self.telemetry_collector.requeue(points)
        return delivered

    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured in system_config."""
        return self.api_client.has_circuit(circuit_id, mode)

    def has_dhw(self) -> bool:
        """Return True if DHW is configured in system_config."""
        return self.api_client.has_dhw

    def has_pool(self) -> bool:
        """Return True if pool heating is configured in system_config."""
        return self.api_client.has_pool

    def _refrigerant_issue_id(self) -> str:
        """Return the repair-issue id for the refrigerant charge alert."""
        return f"refrigerant_charge_alert_{self.config_entry.entry_id}"

    def _update_refrigerant_issue(self) -> None:
        """Raise or clear the refrigerant charge alert repair issue.

        Fixable advisory (WARNING): raised once the alert has persisted for
        several *valid* days, and cleared when the in-season verdict recovers or
        the user confirms the circuit was serviced (the fix flow resets the
        baseline). A frozen alert does NOT self-clear off-season, so its data age
        is annotated: when the domain policy marks the evidence stale, the
        issue switches to the dedicated stale text. It complements and does not
        replace the mandatory F-Gas inspection.
        """
        if not self.refrigerant_detection_active:
            ir.async_delete_issue(self.hass, DOMAIN, self._refrigerant_issue_id())
            return

        status = getattr(self.derived_metrics, "refrigerant_status", None)
        issue_id = self._refrigerant_issue_id()
        alert = refrigerant_alert_policy(status)
        if alert.persistent:
            if alert.stale:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=True,
                    is_persistent=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="refrigerant_charge_alert_stale",
                    translation_placeholders={
                        "last_valid_day": str(status.last_valid_day),
                        "days_since_valid_data": str(status.days_since_valid_data),
                    },
                )
            else:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=True,
                    is_persistent=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="refrigerant_charge_alert",
                )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _external_room_sensor_notice_id(self) -> str:
        """Return the id of the one-time room-regulation notice."""
        return f"external_room_sensor_notice_{self.config_entry.entry_id}"

    def _update_external_room_sensor_notice(self) -> None:
        """Tell the user once how room regulation works without a thermostat.

        Raised when a heating circuit has no Hitachi thermostat reported and
        its External room sensor switch is off: the unit runs on its water
        law. Fine for a water-law or a third-party-thermostat installation,
        but a user expecting room regulation needs to turn the switch on and
        feed the Room temperature. Informational, not a fault: it clears on
        its own once the switch is on and never comes back once confirmed.
        Unread registers leave it untouched, so a single failed read cannot
        make it flap.
        """
        issue_id = self._external_room_sensor_notice_id()
        if self.config_entry.options.get(CONF_EXTERNAL_ROOM_SENSOR_NOTICE):
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        if not self.system_config:
            # Unread this poll: judging on a blank bitfield would flap.
            return
        api = self.api_client
        concerned = False
        for cid in (CIRCUIT_PRIMARY_ID, CIRCUIT_SECONDARY_ID):
            if (
                not self.has_circuit(cid, CIRCUIT_MODE_HEATING)
                or not api.can_write(f"circuit{cid}_thermostat")
                or api.has_room_thermostat(cid)
            ):
                continue
            state = api.external_room_sensor_state(cid)
            if state is None:
                # Flag not read this poll (sentinel or read error): leave the
                # issue as it is rather than toggling it on a blind spot.
                return
            concerned = concerned or not state
        if concerned:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="external_room_sensor_notice",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    async def async_restore_kept_values(self) -> None:
        """Load the gateway's kept values; call before the first poll."""
        self._kept_values_store = Store(
            self.hass,
            KEPT_VALUES_STORE_VERSION,
            f"{DOMAIN}_kept_values_{self.config_entry.entry_id}",
        )
        try:
            stored = await self._kept_values_store.async_load()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to load the kept values", exc_info=True)
        else:
            if isinstance(stored, dict):
                self.api_client.restore_kept_values(stored)
        # Saved as soon as a reference changes, e.g. a switch turned off from
        # Home Assistant, so a power cut right after does not undo it.
        self.api_client.listen_kept_values(self._schedule_kept_values_save)

    def _schedule_kept_values_save(self) -> None:
        """Persist the kept values shortly after a reference changed."""
        if self._kept_values_store is not None:
            self._kept_values_store.async_delay_save(
                self.api_client.kept_values, _KEPT_VALUES_SAVE_DELAY_S
            )

    async def async_flush_kept_values(self) -> None:
        """Persist the gateway's kept values immediately (e.g. on unload)."""
        if self._kept_values_store is not None:
            await self._kept_values_store.async_save(self.api_client.kept_values())

    def _restore_failed_issue_id(self) -> str:
        """Return the repair-issue id for settings a reboot took and that would not stick."""
        return f"kept_values_restore_failed_{self.config_entry.entry_id}"

    async def async_retry_restores(self) -> None:
        """Retry the write-backs that gave up, from the repair issue's fix flow.

        The issue is raised again by the next poll if they still fail.
        """
        self.api_client.retry_restores()
        ir.async_delete_issue(self.hass, DOMAIN, self._restore_failed_issue_id())
        await self.async_request_refresh()

    def _update_kept_values(self) -> None:
        """Report the kept values that would not stick, with a repair issue."""
        issue_id = self._restore_failed_issue_id()
        if self.api_client.restore_failed:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="kept_values_restore_failed",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _alarm_issue_id(self) -> str:
        """Return the repair-issue id for an alarm reported by the unit."""
        return f"unit_alarm_{self.config_entry.entry_id}"

    def _update_alarm_issue(self, alarm_code: str | None) -> None:
        """Raise or clear the repair issue for an alarm reported by the unit.

        Not fixable: the remedy is on the unit itself. The issue names the code
        and when this poll loop first saw it, and clears as soon as the unit
        stops reporting it (#457). A failed read (no code) leaves it as is, so a
        transient read error neither clears it nor resets its start time.
        """
        if alarm_code is None:
            return
        issue_id = self._alarm_issue_id()
        if alarm_code == "alarm_code_0":
            self._alarm_code = None
            self._alarm_since = None
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return

        if alarm_code != self._alarm_code:
            self._alarm_code = alarm_code
            self._alarm_since = dt_util.now()
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=(
                "unit_alarm_outdoor_link"
                if self.api_client.outdoor_link_lost
                else "unit_alarm"
            ),
            translation_placeholders={
                "code": alarm_code.removeprefix("alarm_code_"),
                "since": self._alarm_since.strftime("%Y-%m-%d %H:%M"),
            },
        )

    def _cycling_issue_id(self) -> str:
        """Return the repair-issue id for the short-cycling alert."""
        return f"compressor_short_cycling_{self.config_entry.entry_id}"

    def _update_cycling_issue(self) -> None:
        """Raise or clear the short-cycling repair issue.

        Advisory (WARNING), raised once both fault criteria have held for
        several valid days. Unlike the refrigerant issue this one is not
        fixable: there is no baseline to reset, and the remedy (buffer volume,
        heating curve, unit sizing) is an installation change the integration
        cannot make. It clears on its own as soon as the cycling stops.
        """
        issue_id = self._cycling_issue_id()
        if not self.cycling_detection_active:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return

        status = getattr(self.derived_metrics, "cycling_status", None)
        if cycling_alert_policy(status).persistent:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="compressor_short_cycling",
                translation_placeholders={
                    "period": str(int(CYCLING_PERIOD_THRESHOLD_MIN)),
                },
                learn_more_url=_CYCLING_DOC_URL,
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    async def async_reset_refrigerant_baseline(self, source: str) -> None:
        """Reset the refrigerant detector baseline (after a top-up or service).

        ``source`` tells who asked (``RESET_SOURCE_BUTTON`` or
        ``RESET_SOURCE_SERVICED``); it is counted for the anonymous telemetry.
        """
        if self.derived_metrics is not None:
            await self.derived_metrics.async_reset_refrigerant(source)
        ir.async_delete_issue(self.hass, DOMAIN, self._refrigerant_issue_id())
