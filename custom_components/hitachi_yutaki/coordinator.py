"""DataUpdateCoordinator for Hitachi Yutaki integration."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HitachiApiClient
from .api.base import ReadResult
from .const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODES,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DOMAIN,
)
from .domain.services.defrost_guard import DefrostGuard
from .profiles import HitachiHeatPumpProfile
from .telemetry import (
    InstallationInfo,
    MetricsBatch,
    TelemetryCollector,
    TelemetryLevel,
)
from .telemetry.aggregator import aggregate_metrics
from .telemetry.anonymizer import (
    anonymize_daily_stats,
    anonymize_installation_info,
    anonymize_metric_point,
)

_LOGGER = logging.getLogger(__name__)

_MAX_BACKOFF = timedelta(seconds=300)


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
        self.defrost_guard = DefrostGuard()
        self._normal_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
        self._gateway_not_ready_count: int = 0

        # Telemetry (set by async_setup_entry after creation)
        self.telemetry_collector: TelemetryCollector | None = None
        self.telemetry_client: Any = None  # HttpTelemetryClient or NoopTelemetryClient
        self._telemetry_meta: dict[str, Any] | None = None
        self._installation_info_sent: bool = False
        self.telemetry_last_send: datetime | None = None
        self.telemetry_send_failures: int = 0

        # Daily points accumulator for FULL-level daily stats
        self._daily_points_accumulator: list = []
        self._daily_stats_date: date | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hitachi Yutaki."""
        try:
            if not self.api_client.connected:
                await self.api_client.connect()

            # Build full list of keys and fetch all data
            keys_to_read = (
                self.api_client.register_map.base_keys
                + self.profile.extra_register_keys
            )

            _LOGGER.debug("Reading %d keys from gateway", len(keys_to_read))
            result = await self.api_client.read_values(keys_to_read)

            if result == ReadResult.GATEWAY_NOT_READY:
                self._gateway_not_ready_count += 1
                backoff = min(
                    self._normal_interval * (2**self._gateway_not_ready_count),
                    _MAX_BACKOFF,
                )
                self.update_interval = backoff
                raise UpdateFailed(
                    "Gateway is not ready (initializing or desynchronized)"
                )

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

            # Update defrost guard with fresh data
            water_inlet = data.get("water_inlet_temp")
            water_outlet = data.get("water_outlet_temp")
            delta_t = (
                (water_outlet - water_inlet)
                if water_inlet is not None and water_outlet is not None
                else None
            )
            self.defrost_guard.update(
                is_defrosting=self.api_client.is_defrosting,
                delta_t=delta_t,
            )

            # If we reach here, connection is successful, so delete any connection error issue
            ir.async_delete_issue(self.hass, DOMAIN, "connection_error")

            # Telemetry: collect metrics from this poll cycle
            if self.telemetry_collector is not None:
                self.telemetry_collector.collect(
                    data,
                    is_compressor_running=self.api_client.is_compressor_running,
                    is_defrosting=self.api_client.is_defrosting,
                )

            # Send installation info on first successful poll
            if (
                not self._installation_info_sent
                and self.telemetry_client is not None
                and self._telemetry_meta is not None
            ):
                await self._send_installation_info()
                self._installation_info_sent = True

            # Update timing sensors
            for entity in self.entities:
                if hasattr(entity, "async_update_timing"):
                    await entity.async_update_timing()

            return data

        except UpdateFailed:
            # Re-raise so the generic Exception handler below doesn't
            # turn our intentional UpdateFailed into an HA issue.
            raise

        except Exception as exc:
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

    async def _send_installation_info(self) -> None:
        """Build and send installation info on first successful poll."""
        meta = self._telemetry_meta
        if meta is None:
            return

        has_cooling = self.has_circuit(
            CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING
        ) or self.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)

        has_circuit2 = self.has_circuit(
            CIRCUIT_SECONDARY_ID, "heating"
        ) or self.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING)

        info = InstallationInfo(
            instance_hash=meta["instance_hash"],
            profile=meta["profile"],
            gateway_type=meta["gateway_type"],
            ha_version=meta["ha_version"],
            integration_version=meta["integration_version"],
            power_supply=meta["power_supply"],
            has_dhw=self.has_dhw(),
            has_pool=self.has_pool(),
            has_cooling=has_cooling,
            max_circuits=2 if has_circuit2 else 1,
            has_secondary_compressor=self.profile.supports_secondary_compressor,
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
        )
        info = anonymize_installation_info(info)

        try:
            await self.telemetry_client.send_installation(info)
        except Exception:
            _LOGGER.debug("Failed to send telemetry installation info", exc_info=True)

    async def async_flush_telemetry(self) -> None:
        """Flush telemetry buffer and send data."""
        if (
            self.telemetry_collector is None
            or self.telemetry_client is None
            or self._telemetry_meta is None
        ):
            _LOGGER.debug("Telemetry flush skipped: not configured")
            return

        points = self.telemetry_collector.flush()
        if not points:
            _LOGGER.debug("Telemetry flush: buffer empty, nothing to send")
            return

        instance_hash = self._telemetry_meta["instance_hash"]
        _LOGGER.debug(
            "Telemetry flush: %d points to send (level=%s)",
            len(points),
            self.telemetry_collector.level.value,
        )

        try:
            success = False
            if self.telemetry_collector.level == TelemetryLevel.FULL:
                # Send fine-grained metrics
                anonymized = [anonymize_metric_point(p) for p in points]
                batch = MetricsBatch(instance_hash=instance_hash, points=anonymized)
                success = await self.telemetry_client.send_metrics(batch)

                # Check for day boundary BEFORE adding today's points
                today = date.today()
                if (
                    self._daily_stats_date is not None
                    and self._daily_stats_date != today
                    and self._daily_points_accumulator
                ):
                    # Date changed — send yesterday's accumulated stats
                    stats = aggregate_metrics(
                        instance_hash,
                        self._daily_stats_date,
                        self._daily_points_accumulator,
                    )
                    anonymized_stats = anonymize_daily_stats(stats)
                    await self.telemetry_client.send_daily_stats(anonymized_stats)
                    # Reset accumulator
                    self._daily_points_accumulator = []

                # Accumulate today's points
                self._daily_points_accumulator.extend(points)
                self._daily_stats_date = today
            elif self.telemetry_collector.level == TelemetryLevel.BASIC:
                stats = aggregate_metrics(instance_hash, date.today(), points)
                anonymized_stats = anonymize_daily_stats(stats)
                success = await self.telemetry_client.send_daily_stats(anonymized_stats)
                # Also refresh installation info daily
                await self._send_installation_info()

            if success:
                self.telemetry_last_send = datetime.now(tz=UTC)
                _LOGGER.debug("Telemetry flush: sent successfully")
            else:
                self.telemetry_send_failures += 1
                _LOGGER.warning("Telemetry flush: send returned failure")
        except Exception:
            self.telemetry_send_failures += 1
            _LOGGER.warning("Telemetry flush failed", exc_info=True)

    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured in system_config."""
        return self.api_client.has_circuit(circuit_id, mode)

    def has_dhw(self) -> bool:
        """Return True if DHW is configured in system_config."""
        return self.api_client.has_dhw

    def has_pool(self) -> bool:
        """Return True if pool heating is configured in system_config."""
        return self.api_client.has_pool
