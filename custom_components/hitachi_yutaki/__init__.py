"""The Hitachi Yutaki integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    MAJOR_VERSION,
    MINOR_VERSION,
    __version__ as HA_VERSION,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_interval,
)
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.restore_state import (
    RestoreStateData,
    StoredState,
    async_get as async_get_restore_data,
)
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .adapters.derived_metrics import (
    CYCLING_STORE_VERSION,
    MAINTENANCE_EVENTS_STORE_VERSION,
    REFRIGERANT_STORE_VERSION,
    DerivedMetricsAdapter,
)
from .api import GATEWAY_INFO, HitachiApiClient, create_api_client
from .api.base import UnitBindingStatus
from .api.config_providers import GATEWAY_CONFIG_PROVIDERS, GatewayConfigProvider
from .const import (
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    CONF_CYCLING_DETECTION,
    CONF_ELECTRICITY_PRICE_ENTITY,
    CONF_FLEET_PING,
    CONF_POWER_SUPPLY,
    CONF_REFRIGERANT_DETECTION,
    CONF_TELEMETRY_LEVEL,
    DEFAULT_CYCLING_DETECTION,
    DEFAULT_DEVICE_ID,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_REFRIGERANT_DETECTION,
    DEFAULT_TELEMETRY_LEVEL,
    DEVICE_CIRCUIT_1,
    DEVICE_CIRCUIT_2,
    DEVICE_CONTROL_UNIT,
    DEVICE_DHW,
    DEVICE_GATEWAY,
    DEVICE_POOL,
    DEVICE_PRIMARY_COMPRESSOR,
    DEVICE_SECONDARY_COMPRESSOR,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
)
from .coordinator import HitachiYutakiDataCoordinator
from .entity_migration import async_migrate_entities
from .profiles import PROFILES
from .telemetry import (
    HttpTelemetryClient,
    NoopTelemetryClient,
    TelemetryCollector,
    TelemetryLevel,
)
from .telemetry.anonymizer import hash_device_id, hash_instance_id
from .telemetry.collector import compute_buffer_max_size, compute_collect_stride
from .telemetry.fleet_ping import (
    async_register_fleet_ping,
    async_unregister_fleet_ping,
    is_fleet_ping_enabled,
)

_LOGGER = logging.getLogger(__name__)

# How often buffered telemetry points are sent. Paired with the poll interval
# it also fixes how many points a cycle produces, hence the collect stride.
TELEMETRY_FLUSH_INTERVAL = timedelta(minutes=5)

# Delay before a catch-up flush, when a delivered batch left points behind.
# A flush is capped in bytes, so on the widest profiles one request carries
# fewer points than a 5s poll produces in a cycle and the buffer slowly
# saturates. One extra request per cycle doubles the drain rate. It sits past
# the endpoint's 60s rate-limit window and well before the next regular flush.
TELEMETRY_CATCHUP_DELAY = timedelta(seconds=65)

# `async_get_or_create` takes `via_device_id` since HA 2026.8 and drops the
# identifier-based `via_device` in 2027.8. Older releases only know the latter.
_HAS_VIA_DEVICE_ID = (MAJOR_VERSION, MINOR_VERSION) >= (2026, 8)

# Ceiling on the final flush at unload. The client retries three times with
# backoff, so an unreachable endpoint would otherwise hold up a Home Assistant
# shutdown for the better part of a minute for anonymous, best-effort data.
# Sized for one attempt: past that the points are discarded anyway (#395).
UNLOAD_FLUSH_TIMEOUT = 12

type HitachiYutakiConfigEntry = ConfigEntry[HitachiYutakiDataCoordinator]

_THERMAL_ENERGY_KEYS = (
    "thermal_energy_heating_daily",
    "thermal_energy_heating_total",
    "thermal_energy_cooling_daily",
    "thermal_energy_cooling_total",
)


async def _async_first_refresh(coordinator: HitachiYutakiDataCoordinator) -> None:
    """Run the coordinator's first refresh, deferring setup until data is fresh.

    The gateway can report ``GATEWAY_NOT_READY`` while its H-LINK bus is
    initializing or desynchronized, or while it returns no heat pump data at
    all (Modbus TCP is up, H-LINK is not). Setup must not continue in
    that window: entities are gated on live register data, so an empty first
    read silently drops every capability-gated entity until the next reload,
    leaving devices with no entities (#404). Any failure, ``gateway_not_ready``
    included, raises ``ConfigEntryNotReady`` so HA retries setup with backoff.
    So does a poll that carried no valid ``system_config``.
    """
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as exc:
        if coordinator.gateway_not_ready:
            raise ConfigEntryNotReady(
                "Gateway is not ready (initializing, desynchronized or not "
                "receiving heat pump data); setup will retry"
            ) from exc
        raise
    if coordinator.data.get("system_config") is None:
        # The poll succeeded but system_config was unreadable or filtered as a
        # garbage read: capabilities are unknown, so do not build devices and
        # entities from them.
        raise ConfigEntryNotReady(
            "Gateway returned no valid system configuration (0xFFFF or "
            "unreadable); check that the heat pump and gateway are powered and "
            "connected; setup will retry"
        )


def _live_capabilities(coordinator: HitachiYutakiDataCoordinator) -> dict[str, bool]:
    """Return the unit's capability flags decoded from the last poll's system_config."""
    return {
        "circuit1": coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING)
        or coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING),
        "circuit2": coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING)
        or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING),
        "cooling": coordinator.has_circuit(CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING)
        or coordinator.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING),
        "dhw": coordinator.has_dhw(),
        "pool": coordinator.has_pool(),
    }


def _should_reinit_cop_services(
    *,
    live: dict[str, bool],
    persisted: dict[str, bool],
) -> bool:
    """Decide whether COP services must be re-initialised from LIVE capabilities.

    The COP services were already seeded from the persisted ``system_config``
    (#308). Re-init them only when the live capabilities read by the first
    refresh disagree with the persisted ones (first-time setup, or a capability
    changed on the unit).
    """
    return (
        live["cooling"] != persisted["cooling"]
        or live["dhw"] != persisted["dhw"]
        or live["pool"] != persisted["pool"]
    )


def _get_stored_state(
    restore_data: RestoreStateData, entity_id: str
) -> StoredState | None:
    """Return the stored state of an entity, if any.

    HA 2026.11 removes `last_states` in favour of `async_get_stored_state`
    (stored states are now keyed by entity registry id). Older releases only
    have the dict (#458).
    """
    if hasattr(restore_data, "async_get_stored_state"):
        return restore_data.async_get_stored_state(entity_id)
    return restore_data.last_states.get(entity_id)


async def _async_restore_thermal_energy(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    coordinator: HitachiYutakiDataCoordinator,
) -> None:
    """Restore thermal energy accumulators from HA's last state cache."""
    restore_data = async_get_restore_data(hass)
    entity_registry = er.async_get(hass)

    for key in _THERMAL_ENERGY_KEYS:
        unique_id = f"{entry.entry_id}_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is None:
            continue
        last = _get_stored_state(restore_data, entity_id)
        if (
            last
            and last.state
            and last.state.state not in (None, "unknown", "unavailable", "")
        ):
            with suppress(ValueError, TypeError):
                coordinator.derived_metrics.restore_thermal_energy(
                    key, float(last.state.state)
                )


async def _async_restore_energy_state(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    coordinator: HitachiYutakiDataCoordinator,
) -> None:
    """Restore energy accumulators from HA's last state cache."""
    restore_data = async_get_restore_data(hass)
    entity_registry = er.async_get(hass)

    restore_map = {
        "power_consumption": coordinator.derived_metrics.restore_accumulated_energy,
    }
    if CONF_ELECTRICITY_PRICE_ENTITY in entry.data:
        restore_map["electricity_cost"] = (
            coordinator.derived_metrics.restore_electricity_cost
        )

    for key, restore_fn in restore_map.items():
        unique_id = f"{entry.entry_id}_{key}"
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        last = _get_stored_state(restore_data, entity_id) if entity_id else None
        _LOGGER.debug(
            "Energy restore: key=%s unique_id=%s entity_id=%s in_restore=%s",
            key,
            unique_id,
            entity_id,
            last is not None if entity_id else "no_entity",
        )
        if last is None:
            continue
        if last.state and last.state.state not in (None, "unknown", "unavailable", ""):
            _LOGGER.debug("Energy restore: %s = %s", key, last.state.state)
            with suppress(ValueError, TypeError):
                restore_fn(float(last.state.state))
        else:
            _LOGGER.debug("Energy restore: %s, no valid state", key)


def _unit_issue_ids(entry_id: str) -> tuple[str, str]:
    """Return the per-entry unit identity issue ids (not found, duplicate)."""
    return (f"unit_not_found_{entry_id}", f"unit_duplicate_{entry_id}")


async def _async_bind_unit(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    api_client: HitachiApiClient,
    provider: GatewayConfigProvider,
) -> None:
    """Bind the client to the entry's heat pump unit before the first refresh.

    On a gateway hosting several units, a unit can move to another address
    between two setups (#476). The client locates it and the entry persists
    what it found, so it never reads whichever unit took its place. Raises
    ``ConfigEntryNotReady`` while the gateway is still enumerating its units,
    and with a repair issue when the unit is missing or already bound to
    another entry of the same gateway; the client is closed in that case.
    """
    try:
        await _async_apply_unit_binding(hass, entry, api_client, provider)
    except ConfigEntryNotReady:
        if api_client.connected:
            await api_client.close()
        raise


async def _async_apply_unit_binding(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    api_client: HitachiApiClient,
    provider: GatewayConfigProvider,
) -> None:
    """Apply the outcome of ``async_bind_unit``; see ``_async_bind_unit``."""
    not_found_id, duplicate_id = _unit_issue_ids(entry.entry_id)
    binding = await api_client.async_bind_unit(entry.data)
    placeholders = {"name": entry.title, **binding.placeholders}

    if binding.status is UnitBindingStatus.SETTLING:
        raise ConfigEntryNotReady(
            "Gateway is still enumerating its units; setup will retry"
        )
    if binding.status is UnitBindingStatus.MISSING:
        async_create_issue(
            hass,
            DOMAIN,
            not_found_id,
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="unit_not_found",
            translation_placeholders=placeholders,
        )
        raise ConfigEntryNotReady(
            "Heat pump unit not found on the gateway; setup will retry"
        )
    if binding.status is UnitBindingStatus.UNVERIFIED:
        return
    async_delete_issue(hass, DOMAIN, not_found_id)

    data = {**entry.data, **binding.updates}
    identity = provider.unit_identity(data)
    duplicate = next(
        (
            other
            for other in hass.config_entries.async_entries(DOMAIN)
            if identity is not None
            and other.entry_id != entry.entry_id
            and other.data.get("gateway_type") == data["gateway_type"]
            and provider.same_gateway(other.data, data)
            and provider.unit_identity(other.data) == identity
        ),
        None,
    )
    if duplicate is not None:
        async_create_issue(
            hass,
            DOMAIN,
            duplicate_id,
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="unit_duplicate",
            translation_placeholders={**placeholders, "other": duplicate.title},
        )
        raise ConfigEntryNotReady(
            f"Heat pump unit is already bound to entry {duplicate.title!r}"
        )
    async_delete_issue(hass, DOMAIN, duplicate_id)

    if data != dict(entry.data):
        hass.config_entries.async_update_entry(entry, data=data)


def _build_telemetry_collector(
    entry: HitachiYutakiConfigEntry, telemetry_level: TelemetryLevel
) -> TelemetryCollector:
    """Create the collector, decimated to what a flush cycle can send.

    The scan interval is a user setting with no lower bound. When the poll
    outruns the flush cap the buffer saturates and evicts points silently, so
    collection is thinned at the source instead (#395).
    """
    scan_interval = timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
    stride = compute_collect_stride(scan_interval, TELEMETRY_FLUSH_INTERVAL)
    if stride > 1:
        _LOGGER.info(
            "Telemetry collects 1 poll out of %d: a %ss scan interval produces "
            "more points than a %s flush can send",
            stride,
            entry.data[CONF_SCAN_INTERVAL],
            TELEMETRY_FLUSH_INTERVAL,
        )
    return TelemetryCollector(
        level=telemetry_level,
        buffer_max_size=compute_buffer_max_size(scan_interval, stride),
        collect_stride=stride,
    )


def _via(parent: dr.DeviceEntry) -> dict[str, Any]:
    """Return the keyword linking a device to its parent on this HA version."""
    if _HAS_VIA_DEVICE_ID:
        return {"via_device_id": parent.id}
    return {"via_device": next(iter(parent.identifiers))}


def _schedule_telemetry_flush(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    coordinator: HitachiYutakiDataCoordinator,
) -> None:
    """Flush telemetry every cycle, with a catch-up when a backlog remains."""
    cancel_catchup: CALLBACK_TYPE | None = None

    async def _telemetry_catchup(_now: datetime) -> None:
        nonlocal cancel_catchup
        cancel_catchup = None
        await coordinator.async_flush_telemetry()

    async def _telemetry_flush(_now: datetime) -> None:
        nonlocal cancel_catchup
        delivered = await coordinator.async_flush_telemetry()
        # Only after a delivered batch: a backlog left by a failing send
        # waits for the next cycle rather than doubling the failed requests.
        if (
            delivered
            and coordinator.telemetry_collector.buffer_size
            and cancel_catchup is None
        ):
            cancel_catchup = async_call_later(
                hass, TELEMETRY_CATCHUP_DELAY, _telemetry_catchup
            )

    @callback
    def _cancel_telemetry_catchup() -> None:
        if cancel_catchup is not None:
            cancel_catchup()

    entry.async_on_unload(
        async_track_time_interval(hass, _telemetry_flush, TELEMETRY_FLUSH_INTERVAL)
    )
    entry.async_on_unload(_cancel_telemetry_catchup)


async def _async_setup_fleet_ping(
    hass: HomeAssistant,
    entry: HitachiYutakiConfigEntry,
    coordinator: HitachiYutakiDataCoordinator,
    integration_version: str,
) -> None:
    """Enrol the entry in the fleet ping and manage its one-time notice."""
    # Fleet ping (#468): anonymous, once a day per HA instance, its own consent.
    if is_fleet_ping_enabled(entry.options):
        await async_register_fleet_ping(
            hass, entry.entry_id, integration_version, coordinator.fleet_ping_unit
        )
        entry.async_on_unload(lambda: async_unregister_fleet_ping(hass, entry.entry_id))

    # Fleet ping notice: tell the user once, and let them turn it off. Not
    # needed when telemetry is ON (which implies the ping) or once they chose.
    fleet_ping_notice_id = f"fleet_ping_notice_{entry.entry_id}"
    if (
        CONF_FLEET_PING not in entry.options
        and entry.options.get(CONF_TELEMETRY_LEVEL) != TelemetryLevel.ON.value
    ):
        async_create_issue(
            hass,
            DOMAIN,
            fleet_ping_notice_id,
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="fleet_ping_notice",
        )
    else:
        async_delete_issue(hass, DOMAIN, fleet_ping_notice_id)


async def async_setup_entry(
    hass: HomeAssistant, entry: HitachiYutakiConfigEntry
) -> bool:
    """Set up Hitachi Yutaki from a config entry."""
    _LOGGER.info("Setting up Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    # Check for missing required configuration parameters
    missing_params = []
    if "gateway_type" not in entry.data:
        missing_params.append("gateway_type")
    if "profile" not in entry.data:
        missing_params.append("profile")

    if missing_params:
        # Create a repair issue to guide the user through reconfiguration
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_config_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="missing_config",
        )

        # Return False to prevent setup until repair is completed
        # The user will need to go to the integration options to fix this
        return False

    # Migrate entities from 1.9.x to 2.0.0 format (remove slave_id from unique_id)
    # This must be done before creating new entities to avoid conflicts
    _LOGGER.debug("Checking for entity migrations")
    await async_migrate_entities(hass, entry)

    # Add unique_id if missing (for existing installations)
    if entry.unique_id is None:
        provider = GATEWAY_CONFIG_PROVIDERS[entry.data["gateway_type"]]()
        unit_suffix = provider.unique_id_suffix(entry.data)
        _LOGGER.info(
            "Config entry has no unique_id, attempting to add one based on hardware identifier"
        )

        # Create temporary API client for unique_id retrieval
        temp_client = create_api_client(hass, entry.data)

        unique_id = None
        try:
            if await temp_client.connect():
                hw_id = await temp_client.async_get_unique_id()
                if hw_id:
                    unique_id = f"{DOMAIN}_{hw_id}_{unit_suffix}"
                    _LOGGER.info(
                        "Added hardware-based unique_id to existing config entry: %s",
                        unique_id,
                    )
        except Exception as exc:
            _LOGGER.debug("Error retrieving hardware identifier: %s", exc)
        finally:
            if temp_client.connected:
                await temp_client.close()

        # Preserve the provider's legacy fallback identity for existing entries.
        if unique_id is None:
            unique_id = provider.fallback_unique_id(entry.data)
            _LOGGER.warning(
                "Could not retrieve hardware identifier, using IP-based unique_id: %s",
                unique_id,
            )

        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    # Get gateway and profile from config entry
    # At this point, these should exist (checked above)
    gateway_type = entry.data["gateway_type"]
    profile_key = entry.data["profile"]

    # Get gateway info (must exist)
    if gateway_type not in GATEWAY_INFO:
        raise ValueError(f"Unsupported gateway type: {gateway_type}")
    if profile_key not in PROFILES:
        raise ValueError(f"Unsupported profile: {profile_key}")

    gateway_info = GATEWAY_INFO[gateway_type]
    gateway_manufacturer = gateway_info.manufacturer
    gateway_model = gateway_info.model

    # Instantiate the gateway client and bind it to the entry's unit
    api_client = create_api_client(hass, entry.data)
    await _async_bind_unit(
        hass, entry, api_client, GATEWAY_CONFIG_PROVIDERS[gateway_type]()
    )
    profile = PROFILES[profile_key]()

    coordinator = HitachiYutakiDataCoordinator(hass, entry, api_client, profile)

    # Set up telemetry before first refresh so collector is ready
    telemetry_level_str = entry.options.get(
        CONF_TELEMETRY_LEVEL, DEFAULT_TELEMETRY_LEVEL
    )
    telemetry_level = TelemetryLevel(telemetry_level_str)
    _LOGGER.info(
        "Telemetry level: %s (from options: %s)",
        telemetry_level.value,
        CONF_TELEMETRY_LEVEL in entry.options,
    )

    # Always inject telemetry dependencies (noop when OFF)
    instance_id = await async_get_instance_id(hass)
    instance_hash = hash_instance_id(instance_id)
    # Per-unit identity, keyed on the hardware identifier so deleting and
    # re-adding an entry preserves the unit's fleet history. entry.unique_id is
    # non-None here because the back-fill above always sets one, but the
    # invariant is asserted rather than assumed: a None would hash the literal
    # string "None" and silently give every entry the same identity again.
    if entry.unique_id is None:
        raise ValueError("Config entry has no unique_id after back-fill")
    device_hash = hash_device_id(instance_id, entry.unique_id)
    integration = await async_get_integration(hass, DOMAIN)

    if telemetry_level != TelemetryLevel.OFF:
        session = async_get_clientsession(hass)
        coordinator.telemetry_client = HttpTelemetryClient(
            session, instance_hash, label=entry.title
        )
    else:
        coordinator.telemetry_client = NoopTelemetryClient()

    coordinator.telemetry_collector = _build_telemetry_collector(entry, telemetry_level)
    coordinator._telemetry_meta = {
        "instance_hash": instance_hash,
        "device_hash": device_hash,
        "profile": profile_key,
        "gateway_type": gateway_type,
        "ha_version": HA_VERSION,
        "integration_version": integration.version,
        "power_supply": entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY),
    }

    # Seed capability flags from persisted system_config so COP services are
    # initialised before the first refresh (#308).
    # decode_config tolerates missing/0 values and returns all-False flags for
    # never-yet-refreshed entries.
    persisted_flags = api_client.decode_config(
        {"system_config": entry.data.get("system_config", 0)}
    )
    persisted_has_cooling = persisted_flags.get(
        "has_circuit1_cooling", False
    ) or persisted_flags.get("has_circuit2_cooling", False)
    persisted_has_dhw = persisted_flags.get("has_dhw", False)
    persisted_has_pool = persisted_flags.get("has_pool", False)
    persisted_caps = {
        "cooling": persisted_has_cooling,
        "dhw": persisted_has_dhw,
        "pool": persisted_has_pool,
    }

    refrigerant_detection_enabled = entry.options.get(
        CONF_REFRIGERANT_DETECTION, DEFAULT_REFRIGERANT_DETECTION
    )
    cycling_detection_enabled = entry.options.get(
        CONF_CYCLING_DETECTION, DEFAULT_CYCLING_DETECTION
    )

    # Create derived metrics adapter (enriches data with thermal power, COP, etc.)
    coordinator.derived_metrics = DerivedMetricsAdapter(
        hass=hass,
        config_entry=entry,
        power_supply=entry.data.get(CONF_POWER_SUPPLY, DEFAULT_POWER_SUPPLY),
        has_cooling=persisted_has_cooling,
        has_dhw=persisted_has_dhw,
        has_pool=persisted_has_pool,
        supports_secondary_compressor=profile.supports_secondary_compressor,
        supports_extended_compressor_sensors=profile.supports_extended_compressor_sensors,
        superheat_plausible_range=profile.gas_superheat_plausible_range,
        superheat_observed_band=profile.gas_superheat_observed_band,
        refrigerant_detection_enabled=refrigerant_detection_enabled,
        cycling_detection_enabled=cycling_detection_enabled,
    )

    # Restore the refrigerant-anomaly detector state from its persisted Store
    # BEFORE the first poll: that poll runs _update_refrigerant_issue(), which
    # must see the persisted alert_streak. Restoring afterwards would delete an
    # active refrigerant repair issue and publish a spurious `learning` status
    # for one poll cycle on every Home Assistant restart.
    await coordinator.derived_metrics.async_restore_refrigerant()

    # Same ordering rule for the cycling detector: its repair issue is raised
    # from the first poll, so the persisted alert streak must already be there.
    await coordinator.derived_metrics.async_restore_cycling()

    # Same rule for the energy counters (#432): restore the thermal and
    # electrical accumulators BEFORE the first poll. That poll publishes
    # ``coordinator.data`` for the entities created later in this function, and
    # nothing re-injects a value restored afterwards, so a restore placed after
    # the refresh left ``power_consumption`` (TOTAL_INCREASING) at 0.0 for one
    # poll after every restart: HA statistics read it as a meter reset and
    # re-added the lifetime total.
    await _async_restore_thermal_energy(hass, entry, coordinator)
    await _async_restore_energy_state(hass, entry, coordinator)

    # Initial poll. Setup only continues on fresh register data: entities and
    # devices are gated on the capabilities it carries (#404).
    await _async_first_refresh(coordinator)

    _LOGGER.debug("Data coordinator initialized")

    entry.runtime_data = coordinator

    # Live capabilities read from the fresh first refresh. They gate device
    # registration below, like the entity conditions gate entities.
    caps = _live_capabilities(coordinator)

    # Re-initialise COP services only when the live capabilities disagree with
    # the persisted ones the services were seeded from (#308).
    if _should_reinit_cop_services(live=caps, persisted=persisted_caps):
        coordinator.derived_metrics._has_cooling = caps["cooling"]
        coordinator.derived_metrics._init_cop_services(
            has_cooling=caps["cooling"],
            has_dhw=caps["dhw"],
            has_pool=caps["pool"],
        )

    # Rehydrate COP measurement buffers from Recorder history
    await coordinator.derived_metrics.async_rehydrate_cop()

    # Rehydrate compressor timing from Recorder history
    await coordinator.derived_metrics.async_rehydrate_timing()

    _LOGGER.info("Using Hitachi profile: %s", profile.name)

    # Register devices
    device_registry = dr.async_get(hass)
    _LOGGER.debug("Registering devices for unit model %s", profile.name)

    # Add gateway device
    gateway_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_GATEWAY}")},
        manufacturer=gateway_manufacturer,
        model=gateway_model,
        name=DEVICE_GATEWAY.title(),  # Fallback name
        translation_key="gateway",
        configuration_url=GATEWAY_CONFIG_PROVIDERS[gateway_type]().configuration_url(
            entry.data
        ),
    )

    # Add main unit device
    control_unit_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CONTROL_UNIT}")},
        manufacturer=MANUFACTURER,
        model=profile.name,
        name=DEVICE_CONTROL_UNIT.replace("_", " ").title(),  # Fallback name
        translation_key="control_unit",
        **_via(gateway_device),
    )

    # Add primary compressor device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_PRIMARY_COMPRESSOR}")},
        manufacturer=MANUFACTURER,
        model=profile.name,
        name=DEVICE_PRIMARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
        translation_key="primary_compressor",
        **_via(control_unit_device),
    )

    # Add secondary compressor device for S80 model
    if profile.supports_secondary_compressor:
        _LOGGER.debug("Profile supports secondary compressor, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_SECONDARY_COMPRESSOR}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_SECONDARY_COMPRESSOR.replace("_", " ").title(),  # Fallback name
            translation_key="secondary_compressor",
            **_via(control_unit_device),
        )

    # Add Circuit 1 device if configured
    if caps["circuit1"]:
        _LOGGER.debug("Circuit 1 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_1}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_CIRCUIT_1.replace("_", " ").title(),  # Fallback name
            translation_key="circuit1",
            **_via(control_unit_device),
        )

    # Add Circuit 2 device if configured
    if caps["circuit2"]:
        _LOGGER.debug("Circuit 2 configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_CIRCUIT_2}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_CIRCUIT_2.replace("_", " ").title(),  # Fallback name
            translation_key="circuit2",
            **_via(control_unit_device),
        )

    # Add DHW device if configured
    if caps["dhw"]:
        _LOGGER.debug("DHW configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_DHW}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_DHW.replace("_", " ").capitalize(),  # Fallback name
            translation_key="dhw",
            **_via(control_unit_device),
        )

    # Add Pool device if configured
    if caps["pool"]:
        _LOGGER.debug("Pool configured, registering device")
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_{DEVICE_POOL}")},
            manufacturer=MANUFACTURER,
            model=profile.name,
            name=DEVICE_POOL.replace("_", " ").title(),  # Fallback name
            translation_key="pool",
            **_via(control_unit_device),
        )

    # Energy cost onboarding: suggest price entity configuration
    if CONF_ELECTRICITY_PRICE_ENTITY not in entry.data:
        async_create_issue(
            hass,
            DOMAIN,
            f"enable_energy_cost_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="enable_energy_cost",
        )

    # Telemetry onboarding: create repair issue for existing users who haven't chosen yet
    if CONF_TELEMETRY_LEVEL not in entry.options:
        async_create_issue(
            hass,
            DOMAIN,
            f"enable_telemetry_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="enable_telemetry",
        )

    # Refrigerant detection onboarding: invite existing users on capable profiles
    # to opt into the beta detector. Never shown on profiles without the extended
    # compressor sensors (e.g. Yutampo R32), which cannot run the detector.
    if (
        profile.supports_extended_compressor_sensors
        and CONF_REFRIGERANT_DETECTION not in entry.options
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"enable_refrigerant_detection_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            issue_domain=DOMAIN,
            translation_key="enable_refrigerant_detection",
        )

    # Set up telemetry flush timer
    if telemetry_level != TelemetryLevel.OFF:
        _schedule_telemetry_flush(hass, entry, coordinator)

    await _async_setup_fleet_ping(hass, entry, coordinator, integration.version)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(
        "Hitachi Yutaki integration setup completed for %s", entry.data[CONF_NAME]
    )

    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: HitachiYutakiConfigEntry
) -> bool:
    """Migrate config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 to 2: Add gateway_type and profile if missing
        new_data = {**config_entry.data}

        # Add gateway_type if missing (default to modbus_atw_mbs_02)
        if "gateway_type" not in new_data:
            new_data["gateway_type"] = "modbus_atw_mbs_02"

        # Add profile if missing (will trigger repair flow)
        if "profile" not in new_data:
            # Don't add a default profile - let the repair flow handle it
            pass

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.debug("Migration to version %s successful", config_entry.version)

    if config_entry.version == 2 and config_entry.minor_version < 2:
        # Version 2.1 to 2.2: Prefix Modbus connection keys with "modbus_"
        new_data = {**config_entry.data}

        # host → modbus_host
        if "host" in new_data:
            new_data["modbus_host"] = new_data.pop("host")
        # port → modbus_port
        if "port" in new_data:
            new_data["modbus_port"] = new_data.pop("port")
        # slave → modbus_device_id (direct from v2.1)
        if "slave" in new_data:
            new_data["modbus_device_id"] = new_data.pop("slave")
        elif "modbus_device_id" not in new_data:
            new_data["modbus_device_id"] = DEFAULT_DEVICE_ID

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    if config_entry.version == 2 and config_entry.minor_version < 4:
        # Version 2.3 to 2.4: Add gateway_variant, migrate pre2016 gateway_type
        new_data = {**config_entry.data}

        if "gateway_variant" not in new_data:
            # Handle old pre2016 gateway_type from earlier implementation
            if new_data.get("gateway_type") == "modbus_atw_mbs_02_pre2016":
                new_data["gateway_type"] = "modbus_atw_mbs_02"
                new_data["gateway_variant"] = "gen1"
            else:
                new_data["gateway_variant"] = "gen2"

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=4
        )
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: HitachiYutakiConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing a device the unit does not declare (#404).

    The gateway, control unit and compressors always exist and cannot be
    removed. A circuit, DHW or pool device can, but only when the unit's
    current system_config no longer declares it, e.g. a phantom device left
    by an earlier garbage read.
    """
    if config_entry.state is not ConfigEntryState.LOADED:
        return False
    caps = _live_capabilities(config_entry.runtime_data)
    declared = {
        f"{config_entry.entry_id}_{DEVICE_CIRCUIT_1}": caps["circuit1"],
        f"{config_entry.entry_id}_{DEVICE_CIRCUIT_2}": caps["circuit2"],
        f"{config_entry.entry_id}_{DEVICE_DHW}": caps["dhw"],
        f"{config_entry.entry_id}_{DEVICE_POOL}": caps["pool"],
    }
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN and identifier in declared:
            return not declared[identifier]
    return False


async def async_unload_entry(
    hass: HomeAssistant, entry: HitachiYutakiConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Hitachi Yutaki integration for %s", entry.data[CONF_NAME])

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data

        # Flush remaining telemetry data before closing. One request only:
        # the endpoint accepts one per minute per unit, so draining a deeper
        # backlog here would be rejected anyway. Bounded, so an unreachable
        # endpoint cannot stall the shutdown. Say what is being discarded
        # rather than let it vanish with the coordinator (#395).
        try:
            async with asyncio.timeout(UNLOAD_FLUSH_TIMEOUT):
                await coordinator.async_flush_telemetry()
        except TimeoutError:
            _LOGGER.info(
                "[%s] Telemetry flush on unload timed out after %ds",
                entry.title,
                UNLOAD_FLUSH_TIMEOUT,
            )
        stranded = coordinator.telemetry_collector.buffer_size
        if stranded:
            _LOGGER.info(
                "[%s] %d buffered telemetry point(s) discarded on unload",
                entry.title,
                stranded,
            )

        # Persist preventive-maintenance detector state before closing
        if coordinator.derived_metrics is not None:
            await coordinator.derived_metrics.async_flush_refrigerant()
            await coordinator.derived_metrics.async_flush_cycling()

        # Close API connection
        if coordinator.api_client.connected:
            _LOGGER.debug("Closing API connection")
            await coordinator.api_client.close()

        _LOGGER.info("Hitachi Yutaki integration unloaded successfully")

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: HitachiYutakiConfigEntry
) -> None:
    """Clean up per-entry persistent artefacts when the entry is removed.

    Called by HA after unload, once the entry is already gone from the
    registry, so ``entry.runtime_data`` is unavailable here.
    """
    # Refrigerant detector Store (.storage/hitachi_yutaki_refrigerant_<entry_id>).
    # Only extended-sensor profiles create it; async_remove is a no-op otherwise.
    await Store(
        hass, REFRIGERANT_STORE_VERSION, f"{DOMAIN}_refrigerant_{entry.entry_id}"
    ).async_remove()
    # Cycling detector Store and the reset counters kept beside the detectors.
    await Store(
        hass, CYCLING_STORE_VERSION, f"{DOMAIN}_cycling_{entry.entry_id}"
    ).async_remove()
    await Store(
        hass,
        MAINTENANCE_EVENTS_STORE_VERSION,
        f"{DOMAIN}_maintenance_events_{entry.entry_id}",
    ).async_remove()

    # Per-entry repair issues (async_delete_issue is idempotent).
    for issue_id in (
        f"missing_config_{entry.entry_id}",
        f"enable_energy_cost_{entry.entry_id}",
        f"enable_telemetry_{entry.entry_id}",
        f"fleet_ping_notice_{entry.entry_id}",
        f"enable_refrigerant_detection_{entry.entry_id}",
        f"refrigerant_charge_alert_{entry.entry_id}",
        f"compressor_short_cycling_{entry.entry_id}",
        *_unit_issue_ids(entry.entry_id),
    ):
        async_delete_issue(hass, DOMAIN, issue_id)

    # Domain-global issues are shared across entries: sweep them only when the
    # removed entry was the last one. Recent HA calls this once the entry is
    # out of the registry, older releases (2025.1) while it is still listed.
    if not any(
        other.entry_id != entry.entry_id
        for other in hass.config_entries.async_entries(DOMAIN)
    ):
        for issue_id in ("connection_error", "desync_warning", "initializing_warning"):
            async_delete_issue(hass, DOMAIN, issue_id)
