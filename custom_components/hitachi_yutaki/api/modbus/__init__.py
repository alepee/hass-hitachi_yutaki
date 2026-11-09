"""Modbus client for Hitachi heat pumps."""

from collections.abc import Awaitable, Callable, Mapping
import logging
import time
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from ...const import (
    CIRCUIT_IDS,
    CIRCUIT_MODE_COOLING,
    CIRCUIT_MODE_HEATING,
    CIRCUIT_MODES,
    CIRCUIT_PRIMARY_ID,
    CIRCUIT_SECONDARY_ID,
    DOMAIN,
)
from ..base import GatewayCommunicationError, HitachiApiClient, ReadResult
from .kept_values import KeptValues
from .outage import GatewayOutage, NotReadyWarning
from .registers import HitachiRegisterMap, RegisterDefinition
from .registers.atw_mbs_02 import AtwMbs02RegisterMap
from .transport import ModbusTransport

_LOGGER = logging.getLogger(__name__)

# How long a successful write shadows its STATUS register: the gateway takes
# 15-20 s (H-LINK round trip) to reflect a CONTROL write, so polls in between
# report the old value. Past this the gateway value wins again.
PENDING_WRITE_TTL = 30.0


class ModbusApiClient(HitachiApiClient):
    """Modbus client for Hitachi heat pumps.

    Holds the gateway logic (register maps, sentinels, module gating, pending
    writes). Every register access goes through a :class:`ModbusTransport`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str,
        port: int,
        slave: int,
        register_map: HitachiRegisterMap | None = None,
        transport: ModbusTransport | None = None,
    ) -> None:
        """Initialize the Modbus client.

        ``transport`` defaults to a Modbus TCP connection to ``host:port``
        addressing device ``slave``.
        """
        self._hass = hass
        self._name = name
        self._transport = transport or ModbusTransport(hass, host, port, slave)
        self._data = {}
        self._register_map: HitachiRegisterMap = register_map or AtwMbs02RegisterMap()
        self._outage = GatewayOutage()
        # key -> (expected deserialized value, monotonic deadline)
        self._pending_writes: dict[str, tuple[Any, float]] = {}
        # Values the hardware forgets on reboot (#511), see ``Keep``.
        self._kept = KeptValues(
            self._register_map.all_registers, self._register_map.writable_keys
        )
        # Key being written back, so that write is not mistaken for a command.
        self._writing_back: str | None = None

    @property
    def register_map(self) -> HitachiRegisterMap:
        """Return the register map for the gateway."""
        return self._register_map

    @property
    def base_keys(self) -> list[str]:
        """Return the keys needed for a normal data refresh."""
        return list(self._register_map.base_keys)

    @property
    def gateway_keys(self) -> list[str]:
        """Return the keys needed to validate the gateway."""
        return list(self._register_map.gateway_keys)

    def supports_key(self, key: str) -> bool:
        """Return whether the register map exposes this key."""
        return key in self._register_map.all_registers

    def can_write(self, key: str) -> bool:
        """Return whether the register map accepts writes for this key."""
        return self.supports_key(key) and key in self._register_map.writable_keys

    @property
    def supported_unit_modes(self) -> tuple[str, ...]:
        """Return the global modes supported by writable registers."""
        if not self.can_write("unit_mode"):
            return ()
        rmap = self._register_map
        return tuple(
            mode
            for mode, value in (
                ("cool", rmap.hvac_unit_mode_cool),
                ("heat", rmap.hvac_unit_mode_heat),
                ("auto", rmap.hvac_unit_mode_auto),
            )
            if value is not None
        )

    async def connect(self) -> bool:
        """Connect to the API."""
        return await self._transport.connect()

    async def close(self) -> bool:
        """Close the connection to the API, best effort.

        Never raises: callers close in ``finally`` blocks and on unload, where
        a failing close must not replace their result. Returns False when the
        connection could not be closed cleanly.
        """
        try:
            await self._transport.close()
        except GatewayCommunicationError as exc:
            _LOGGER.debug("Error closing connection to Modbus gateway: %s", exc)
            return False
        return True

    @property
    def connected(self) -> bool:
        """Return True if the client is connected to the API."""
        return self._transport.connected

    @property
    def capabilities(self) -> dict:
        """Return the capabilities of the gateway."""
        return self._data.get("capabilities", {})

    async def get_model_key(self) -> str:
        """Return the model of the heat pump."""
        return self._data.get("unit_model")

    async def async_get_unique_id(self) -> str | None:
        """Get a unique hardware identifier from Modbus input registers.

        Reads Input Registers 0-2 (function code 04) which contain
        hardware-specific values that form a stable unique identifier.

        Returns:
            A string in format "REG0-REG1-REG2" (e.g., "3846-103-56")
            or None if the registers cannot be read.

        """
        try:
            registers = await self._transport.read_input_registers(0, 3)

            if registers is None:
                _LOGGER.warning("Failed to read input registers for unique_id")
                return None

            if len(registers) >= 3:
                unique_id = f"{registers[0]}-{registers[1]}-{registers[2]}"
                _LOGGER.debug(
                    "Read hardware identifier from input registers: %s",
                    unique_id,
                )
                return unique_id

            _LOGGER.warning(
                "Unexpected number of registers returned: %d (expected 3)",
                len(registers),
            )
            return None

        except GatewayCommunicationError as exc:
            _LOGGER.warning(
                "Communication error reading input registers for unique_id: %s",
                exc,
            )
            return None

    async def read_value(self, key: str) -> Any:
        """Read a value from the API."""
        return self._data.get(key)

    async def write_value(self, key: str, value: int) -> bool:
        """Write a value to the API."""
        if key not in self._register_map.writable_keys:
            _LOGGER.error("Unknown or non-writable register key: %s", key)
            return False

        reg = self._register_map.all_registers[key]
        register_address = (
            reg.write_address if reg.write_address is not None else reg.address
        )
        try:
            accepted = await self._with_reconnect(
                f"write to register {key}",
                lambda: self._transport.write_register(register_address, value),
            )
        except GatewayCommunicationError as exc:
            _LOGGER.error("Error writing to register %s: %s", key, exc)
            return False

        if not accepted:
            # The gateway answered, so the link is fine: a reconnection and a
            # second write cannot fix what made it refuse the command.
            _LOGGER.error("Gateway refused write to register %s", key)
            return False

        self._shadow_written_value(key, reg, value)
        return True

    async def _with_reconnect[T](
        self, operation: str, attempt: Callable[[], Awaitable[T]]
    ) -> T:
        """Run ``attempt``, reconnecting and running it once more on a link failure.

        A failed reconnection, or a second failure, propagates the
        :class:`GatewayCommunicationError`.
        """
        try:
            return await attempt()
        except GatewayCommunicationError as exc:
            _LOGGER.warning(
                "Communication error during %s: %s. Attempting reconnection...",
                operation,
                exc,
            )
            if not await self._transport.reconnect():
                _LOGGER.error("Reconnection failed, %s aborted", operation)
                raise
        _LOGGER.warning("Reconnection successful, retrying %s", operation)
        return await attempt()

    @property
    def has_dhw(self) -> bool:
        """Return True if DHW is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & self._register_map.mask_dhw)

    def has_circuit(self, circuit_id: CIRCUIT_IDS, mode: CIRCUIT_MODES) -> bool:
        """Return True if circuit is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(
            system_config & self._register_map.masks_circuit.get((circuit_id, mode))
        )

    def has_room_thermostat(self, circuit_id: CIRCUIT_IDS) -> bool:
        """Return True if the unit reports a Hitachi room thermostat on the circuit."""
        system_config = self._data.get("system_config", 0)
        mask = self._register_map.masks_circuit_thermostat.get(circuit_id, 0)
        return bool(system_config & mask)

    @property
    def has_pool(self) -> bool:
        """Return True if pool heating is configured."""
        system_config = self._data.get("system_config", 0)
        return bool(system_config & self._register_map.mask_pool)

    def decode_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decode raw config data into a dictionary of boolean flags.

        Defensive: treats a missing or ``None`` ``system_config`` as ``0``
        (no modules detected) instead of raising ``TypeError``. Callers should
        still avoid passing unread data (see :class:`ReadResult` contract).
        """
        # `or 0` (not the dict default) so a None value also falls back to 0.
        system_config = data.get("system_config") or 0
        rmap = self._register_map
        decoded = data.copy()
        decoded["has_dhw"] = bool(system_config & rmap.mask_dhw)
        decoded["has_circuit1_heating"] = bool(
            system_config
            & rmap.masks_circuit.get((CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_HEATING))
        )
        decoded["has_circuit1_cooling"] = bool(
            system_config
            & rmap.masks_circuit.get((CIRCUIT_PRIMARY_ID, CIRCUIT_MODE_COOLING))
        )
        decoded["has_circuit2_heating"] = bool(
            system_config
            & rmap.masks_circuit.get((CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING))
        )
        decoded["has_circuit2_cooling"] = bool(
            system_config
            & rmap.masks_circuit.get((CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING))
        )
        decoded["has_pool"] = bool(system_config & rmap.mask_pool)
        return decoded

    def _gate_unconfigured_modules(self) -> None:
        """Remove data for modules not present in system_config.

        Prevents propagation of default/stale register values for modules
        that are not physically installed (e.g. DHW target temp = 45 on a
        unit without DHW). This ensures all downstream consumers (entities,
        telemetry) only see data for modules that actually exist.
        """
        rmap = self._register_map

        if not self.has_dhw:
            for key in rmap.dhw_keys:
                self._data.pop(key, None)

        if not self.has_pool:
            for key in rmap.pool_keys:
                self._data.pop(key, None)

        if not self.has_circuit(
            CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_HEATING
        ) and not self.has_circuit(CIRCUIT_SECONDARY_ID, CIRCUIT_MODE_COOLING):
            for key in rmap.circuit_2_keys:
                self._data.pop(key, None)

    @property
    def outdoor_link_lost(self) -> bool:
        """Return whether the unit reports it cannot reach its outdoor unit."""
        return self._data.get("alarm_code") in self._register_map.outdoor_link_alarms

    def _gate_outdoor_link_loss(self) -> None:
        """Remove the outdoor readings zeroed by a lost outdoor unit (#457).

        On alarm 03 the indoor unit no longer hears from the outdoor unit and
        reports 0 for every reading it relays from it. 0 is also a valid
        temperature, so only zeros are dropped, and only during that alarm: an
        auxiliary outdoor sensor wired to the indoor unit keeps its real value.
        """
        if not self.outdoor_link_lost:
            return
        for key in self._register_map.outdoor_unit_keys:
            if self._data.get(key) == 0:
                self._data.pop(key)

    # Internal marker to distinguish sentinel-filtered None from read errors
    _SENTINEL_FILTERED = object()

    def _shadow_written_value(
        self, key: str, definition: RegisterDefinition, raw: int
    ) -> None:
        """Publish a written value at once and shadow STATUS reads of ``key``.

        The expected value is the deserialized raw value, i.e. what a STATUS
        read reports once the unit has applied the command.
        """
        expected = definition.deserializer(raw) if definition.deserializer else raw
        if expected is None:
            return
        self._data[key] = expected
        self._pending_writes[key] = (expected, time.monotonic() + PENDING_WRITE_TTL)
        self._kept.written(key, expected, by_restore=self._writing_back == key)

    def _is_shadowed_by_pending_write(self, key: str, value: Any) -> bool:
        """Return True when a fresh STATUS read of ``key`` must be ignored.

        A read equal to the expected value confirms the write; one past the
        deadline yields to the gateway, so a refused command cannot stick.
        """
        pending = self._pending_writes.get(key)
        if pending is None:
            return False
        expected, deadline = pending
        if value == expected:
            del self._pending_writes[key]
            return False
        if time.monotonic() >= deadline:
            del self._pending_writes[key]
            _LOGGER.debug(
                "Write of %s=%s not confirmed within %.0f s, gateway reports %s",
                key,
                expected,
                PENDING_WRITE_TTL,
                value,
            )
            return False
        return True

    async def restore_lost_values(self) -> None:
        """Write back the kept values the last successful read found lost (#511).

        Mechanical: each value goes back raw, through its register's
        serializer, in the order :class:`KeptValues` plans from the ``Keep``
        declarations. A write-back is confirmed by the pending-write shadow.
        """
        all_regs = self._register_map.all_registers
        for key, value in self._kept.plan(self._data, self._pending_writes):
            if not self._kept.wanted(key, value):
                continue  # Home Assistant wrote it while earlier values went back.
            serializer = all_regs[key].serializer
            self._writing_back = key
            try:
                written = await self.write_value(
                    key, serializer(value) if serializer else int(value)
                )
            finally:
                self._writing_back = None
            if not written:
                _LOGGER.warning("Writing %s back failed", key)

    def kept_values(self) -> dict[str, Any]:
        """Return the references of the values the hardware forgets on reboot."""
        return self._kept.snapshot()

    def restore_kept_values(self, values: Mapping[str, Any]) -> None:
        """Load persisted references, e.g. before the first poll after a restart."""
        self._kept.load(values)

    def listen_kept_values(self, listener: Callable[[], None]) -> None:
        """Call ``listener`` whenever a reference changes, to persist it."""
        self._kept.listen(listener)

    def retry_restores(self) -> None:
        """Give every value that could not be written back a fresh set of attempts."""
        self._kept.retry()

    @property
    def restore_failed(self) -> bool:
        """Return True while a lost value could not be written back."""
        return self._kept.failed

    async def _read_register(self, definition: RegisterDefinition) -> Any:
        """Read and deserialize a single register.

        Returns the deserialized value, _SENTINEL_FILTERED when the value is a
        gateway sentinel (unavailable sensor/module), or None when no fresh
        value is available. None covers both a Modbus read error
        (``result.isError()``) and a deserializer that maps a sensor-error raw
        value (e.g. 0xFFFF) to ``None``. Callers must treat a remaining None
        (after any fallback) as "no value" and clear the stored reading rather
        than retaining a stale one (see :meth:`read_values`, issue #320).
        """
        registers = await self._transport.read_holding_registers(definition.address)
        if not registers:
            return None
        value = registers[0]
        if definition.deserializer:
            value = definition.deserializer(value)
        if (
            value is not None
            and definition.sentinel_values
            and value in definition.sentinel_values
        ):
            return self._SENTINEL_FILTERED
        return value

    async def read_values(self, keys: list[str]) -> ReadResult:
        """Fetch data from the heat pump for the given keys.

        Always performs a preflight read of ``system_state``. If the gateway
        reports an unhealthy state (initializing or desynchronized), returns
        ``ReadResult.GATEWAY_NOT_READY`` WITHOUT reading any of the requested
        keys — only ``system_state`` is populated in ``_data``. Callers must
        check the return value before consuming ``read_value()`` output. See
        :class:`ReadResult` for the full contract.

        A communication failure triggers one reconnection and one more read
        cycle; if that fails too, the error propagates.
        """
        self._kept.discard_lost()
        try:
            return await self._with_reconnect(
                "read_values", lambda: self._read_cycle(keys)
            )
        except GatewayCommunicationError as exc:
            _LOGGER.warning("Modbus error during read_values: %s", exc)
            raise

    async def _read_cycle(self, keys: list[str]) -> ReadResult:
        """Run one read cycle: preflight, readiness, key reads, gating, tracking."""
        raw_state = await self._read_system_state()
        if not self._check_readiness(raw_state):
            return ReadResult.GATEWAY_NOT_READY

        all_regs = self._register_map.all_registers
        # A dict, so a key listed twice is read once.
        registers_to_read = {key: all_regs[key] for key in keys if key in all_regs}
        fresh: list[str] = []
        for name, definition in registers_to_read.items():
            value = await self._read_with_fallback(definition)
            if self._store_reading(name, definition, value):
                fresh.append(name)

        # Remove data for modules not declared in system_config
        self._gate_unconfigured_modules()
        self._gate_outdoor_link_loss()

        self._kept.track(fresh, self._data)
        return ReadResult.SUCCESS

    async def _read_system_state(self) -> int:
        """Read ``system_state`` (preflight), store it deserialized, return it raw.

        Raises :class:`GatewayCommunicationError` when the gateway answers the
        preflight with an exception response.
        """
        definition = self._register_map.all_registers["system_state"]
        preflight = await self._transport.read_holding_registers(definition.address)
        if not preflight:
            raise GatewayCommunicationError("Preflight check failed")

        raw_state = preflight[0]
        # Always store the deserialized value for entity consumption
        self._data["system_state"] = (
            definition.deserializer(raw_state) if definition.deserializer else raw_state
        )
        return raw_state

    def _check_readiness(self, raw_state: int) -> bool:
        """Raise or clear the not-ready repair issues; return True when ready.

        Issues are checked in declaration order: the ones before the matching
        state are cleared, the matching one is raised and the check stops.
        """
        for issue_state, issue_key in self._register_map.system_state_issues.items():
            if raw_state == issue_state:
                ir.async_create_issue(
                    self._hass,
                    DOMAIN,
                    issue_key,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=issue_key,
                )
                self._log_not_ready(raw_state)
                return False
            ir.async_delete_issue(self._hass, DOMAIN, issue_key)

        elapsed = self._outage.ready(time.monotonic())
        if elapsed is not None:
            seconds = int(elapsed)
            _LOGGER.warning(
                "Gateway recovered (state: %s) after being not-ready for %d min %d s.",
                raw_state,
                seconds // 60,
                seconds % 60,
            )
        return True

    def _log_not_ready(self, raw_state: int) -> None:
        """Warn about a not-ready gateway, throttled by :class:`GatewayOutage`."""
        now = time.monotonic()
        warning = self._outage.not_ready(now)
        if warning is NotReadyWarning.FIRST:
            _LOGGER.warning(
                "Gateway is not ready (state: %s), skipping further reads for this cycle.",
                raw_state,
            )
        elif warning is NotReadyWarning.REMINDER:
            _LOGGER.warning(
                "Gateway still not ready (state: %s), ongoing for %d minutes.",
                raw_state,
                int(self._outage.duration(now)) // 60,
            )

    async def _read_with_fallback(self, definition: RegisterDefinition) -> Any:
        """Read a register, then its fallback when no value came back.

        Falls back on any None (read error or a sensor-error raw value such as
        0xFFFF deserialized to None), but not on a sentinel: a sentinel means
        the module is known-absent, so there is no point trying.
        """
        value = await self._read_register(definition)
        if value is None and definition.fallback:
            value = await self._read_register(definition.fallback)
        return value

    def _store_reading(
        self, name: str, definition: RegisterDefinition, value: Any
    ) -> bool:
        """Store one reading in ``_data``; return True when it is a fresh value.

        A reading shadowed by a pending write is ignored. A sentinel or a
        missing value clears the stored one, so the entity goes unavailable
        instead of reporting a frozen value (#320).
        """
        if self._is_shadowed_by_pending_write(name, value):
            return False
        if value is self._SENTINEL_FILTERED:
            # Sensor/module unavailable — clear any stale value
            self._data.pop(name, None)
            return False
        if value is None:
            # No fresh value: a sensor-error raw value (e.g. 0xFFFF)
            # deserialized to None, or a read error, with no working fallback.
            self._data.pop(name, None)
            _LOGGER.debug(
                "Clearing %s (no fresh value: sensor error or read error at %s)",
                name,
                definition.address,
            )
            return False
        self._data[name] = value
        return True

    @property
    def is_defrosting(self) -> bool:
        """Return True if the unit is in defrost mode."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_defrost)

    @property
    def is_solar_active(self) -> bool:
        """Return True if solar system is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_solar)

    @property
    def is_pump1_running(self) -> bool:
        """Return True if pump 1 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_pump1)

    @property
    def is_pump2_running(self) -> bool:
        """Return True if pump 2 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_pump2)

    @property
    def is_pump3_running(self) -> bool:
        """Return True if pump 3 is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_pump3)

    @property
    def is_compressor_running(self) -> bool:
        """Return True if compressor is running."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_compressor)

    @property
    def is_boiler_active(self) -> bool:
        """Return True if backup boiler is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_boiler)

    @property
    def is_dhw_heater_active(self) -> bool:
        """Return True if DHW electric heater is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_dhw_heater)

    @property
    def is_space_heater_active(self) -> bool:
        """Return True if space heating electric heater is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_space_heater)

    @property
    def is_smart_function_active(self) -> bool:
        """Return True if smart grid function is active."""
        system_status = self._data.get("system_status", 0)
        return bool(system_status & self._register_map.mask_smart_function)

    @property
    def is_primary_compressor_running(self) -> bool:
        """Return True if primary compressor is running."""
        frequency = self._data.get("compressor_frequency")
        return frequency is not None and frequency > 0

    @property
    def is_secondary_compressor_running(self) -> bool:
        """Return True if secondary compressor is running."""
        frequency = self._data.get("secondary_compressor_frequency")
        return frequency is not None and frequency > 0

    @property
    def is_antilegionella_active(self) -> bool:
        """Return True if anti-legionella cycle is running."""
        status = self._data.get("dhw_antilegionella_status")
        return status == 1

    async def _trigger_refresh(self) -> None:
        """Trigger a refresh of coordinator data after a write operation."""
        # Note: Refresh is handled by coordinator.async_request_refresh() in entities
        return

    # Unit control - Getters
    def get_unit_power(self) -> bool | None:
        """Get the main unit power state."""
        value = self._data.get("unit_power")
        if value is None:
            return None
        return bool(value)

    def get_eco_mode(self) -> bool | None:
        """Get the global eco mode state (pre-2016 units only).

        Returns True if eco mode is on, False if off, None if not available.
        Register 1027: 0=off, 1=on (non-inverted).
        """
        value = self._data.get("eco_mode")
        if value is None:
            return None
        return bool(value)

    def get_eco_offset(self) -> int | None:
        """Get global Eco Offset value (pre-2016 only, register 1090)."""
        return self._data.get("eco_offset")

    async def set_eco_offset(self, offset: int) -> bool:
        """Write the global ECO offset (CONTROL register, valid range 1~10)."""
        if not (1 <= offset <= 10):
            _LOGGER.warning(
                "eco_offset %s is out of range 1~10, write rejected", offset
            )
            return False
        return await self.write_value("eco_offset", offset)

    async def set_eco_mode(self, enabled: bool) -> bool:
        """Enable (1=ECO) or disable (0=Comfort) global ECO mode by writing to addr 1027."""
        return await self.write_value("eco_mode", 1 if enabled else 0)

    def get_unit_mode(self):
        """Get the current unit mode."""
        unit_mode = self._data.get("unit_mode")
        if unit_mode is None:
            return None
        rmap = self._register_map
        mode_map = {
            rmap.hvac_unit_mode_cool: HVACMode.COOL,
            rmap.hvac_unit_mode_heat: HVACMode.HEAT,
        }
        if rmap.hvac_unit_mode_auto is not None:
            mode_map[rmap.hvac_unit_mode_auto] = HVACMode.AUTO
        return mode_map.get(unit_mode)

    def get_operation_state(self) -> str | None:
        """Get the deserialized unit operation state (e.g. heat_thermo_on)."""
        return self._data.get("operation_state")

    # Unit control - Setters
    async def set_unit_power(self, enabled: bool) -> bool:
        """Enable/disable the main heat pump unit."""
        return await self.write_value("unit_power", 1 if enabled else 0)

    async def set_unit_mode(self, mode) -> bool:
        """Set the unit operation mode."""
        rmap = self._register_map
        mode_map = {
            HVACMode.COOL: rmap.hvac_unit_mode_cool,
            HVACMode.HEAT: rmap.hvac_unit_mode_heat,
        }
        if rmap.hvac_unit_mode_auto is not None:
            mode_map[HVACMode.AUTO] = rmap.hvac_unit_mode_auto
        unit_mode = mode_map.get(mode)
        if unit_mode is None:
            return False
        return await self.write_value("unit_mode", unit_mode)

    # Circuit control - Getters
    def get_circuit_power(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get circuit power state."""
        key = f"circuit{circuit_id}_power"
        value = self._data.get(key)
        if value is None:
            return None
        return bool(value)

    def get_circuit_current_temperature(self, circuit_id: CIRCUIT_IDS) -> float | None:
        """Get current temperature for a circuit (already deserialized by register)."""
        key = f"circuit{circuit_id}_current_temp"
        temp = self._data.get(key)
        if temp is None:
            return None
        return float(temp)

    def get_circuit_target_temperature(self, circuit_id: CIRCUIT_IDS) -> float | None:
        """Get target temperature for a circuit (already deserialized by register)."""
        key = f"circuit{circuit_id}_target_temp"
        temp = self._data.get(key)
        if temp is None:
            return None
        return float(temp)

    def get_circuit_eco_mode(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get ECO mode state for a circuit (True=ECO, False=COMFORT)."""
        key = f"circuit{circuit_id}_eco_mode"
        value = self._data.get(key)
        if value is None:
            return None
        # Note: eco_mode uses inverted logic (0=eco, 1=comfort)
        return value == 0

    def get_circuit_thermostat(self, circuit_id: CIRCUIT_IDS) -> bool | None:
        """Get Modbus thermostat state for a circuit."""
        key = f"circuit{circuit_id}_thermostat"
        value = self._data.get(key)
        if value is None:
            return None
        return bool(value)

    def get_circuit_otc_method_heating(self, circuit_id: CIRCUIT_IDS) -> str | None:
        """Get OTC calculation method for heating."""
        key = f"circuit{circuit_id}_otc_calculation_method_heating"
        return self._data.get(key)

    def get_circuit_otc_method_cooling(self, circuit_id: CIRCUIT_IDS) -> str | None:
        """Get OTC calculation method for cooling."""
        key = f"circuit{circuit_id}_otc_calculation_method_cooling"
        return self._data.get(key)

    def get_circuit_max_flow_temp_heating(
        self, circuit_id: CIRCUIT_IDS
    ) -> float | None:
        """Get maximum heating water temperature for OTC (in °C, stored as integer)."""
        key = f"circuit{circuit_id}_max_flow_temp_heating_otc"
        value = self._data.get(key)
        if value is None:
            return None
        return float(value)

    def get_circuit_max_flow_temp_cooling(
        self, circuit_id: CIRCUIT_IDS
    ) -> float | None:
        """Get maximum cooling water temperature for OTC (in °C, stored as integer)."""
        key = f"circuit{circuit_id}_max_flow_temp_cooling_otc"
        value = self._data.get(key)
        if value is None:
            return None
        return float(value)

    def get_circuit_heat_eco_offset(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get temperature offset for ECO heating mode (in °C)."""
        key = f"circuit{circuit_id}_heat_eco_offset"
        return self._data.get(key)

    def get_circuit_cool_eco_offset(self, circuit_id: CIRCUIT_IDS) -> int | None:
        """Get temperature offset for ECO cooling mode (in °C)."""
        key = f"circuit{circuit_id}_cool_eco_offset"
        return self._data.get(key)

    # Circuit control - Setters
    async def set_circuit_power(self, circuit_id: CIRCUIT_IDS, enabled: bool) -> bool:
        """Enable/disable a heating/cooling circuit."""
        key = f"circuit{circuit_id}_power"
        return await self.write_value(key, 1 if enabled else 0)

    async def set_circuit_target_temperature(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set target temperature for a circuit."""
        key = f"circuit{circuit_id}_target_temp"
        value = int(temperature * 10)
        return await self.write_value(key, value)

    async def set_circuit_room_temperature(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set measured room temperature for a circuit."""
        key = f"circuit{circuit_id}_current_temp"
        value = int(temperature * 10)
        return await self.write_value(key, value)

    async def set_circuit_eco_mode(
        self, circuit_id: CIRCUIT_IDS, enabled: bool
    ) -> bool:
        """Enable/disable ECO mode for a circuit."""
        key = f"circuit{circuit_id}_eco_mode"
        # Note: eco_mode uses inverted logic (0=eco, 1=comfort)
        value = 0 if enabled else 1
        return await self.write_value(key, value)

    async def set_circuit_thermostat(
        self, circuit_id: CIRCUIT_IDS, enabled: bool
    ) -> bool:
        """Enable/disable Modbus thermostat for a circuit."""
        key = f"circuit{circuit_id}_thermostat"
        return await self.write_value(key, 1 if enabled else 0)

    async def set_circuit_otc_method_heating(
        self, circuit_id: CIRCUIT_IDS, method: str
    ) -> bool:
        """Set OTC calculation method for heating."""
        key = f"circuit{circuit_id}_otc_calculation_method_heating"
        return await self.write_value(
            key, self._register_map.serialize_otc_method_heating(method)
        )

    async def set_circuit_otc_method_cooling(
        self, circuit_id: CIRCUIT_IDS, method: str
    ) -> bool:
        """Set OTC calculation method for cooling."""
        key = f"circuit{circuit_id}_otc_calculation_method_cooling"
        return await self.write_value(
            key, self._register_map.serialize_otc_method_cooling(method)
        )

    async def set_circuit_max_flow_temp_heating(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set maximum heating water temperature for OTC (stored as integer degrees)."""
        key = f"circuit{circuit_id}_max_flow_temp_heating_otc"
        return await self.write_value(key, int(temperature))

    async def set_circuit_max_flow_temp_cooling(
        self, circuit_id: CIRCUIT_IDS, temperature: float
    ) -> bool:
        """Set maximum cooling water temperature for OTC (stored as integer degrees)."""
        key = f"circuit{circuit_id}_max_flow_temp_cooling_otc"
        return await self.write_value(key, int(temperature))

    async def set_circuit_heat_eco_offset(
        self, circuit_id: CIRCUIT_IDS, offset: int
    ) -> bool:
        """Set temperature offset for ECO heating mode."""
        key = f"circuit{circuit_id}_heat_eco_offset"
        return await self.write_value(key, offset)

    async def set_circuit_cool_eco_offset(
        self, circuit_id: CIRCUIT_IDS, offset: int
    ) -> bool:
        """Set temperature offset for ECO cooling mode."""
        key = f"circuit{circuit_id}_cool_eco_offset"
        return await self.write_value(key, offset)

    # DHW control - Getters
    def get_dhw_power(self) -> bool | None:
        """Get DHW power state."""
        value = self._data.get("dhw_power")
        if value is None:
            return None
        return bool(value)

    def get_dhw_current_temperature(self) -> float | None:
        """Get current DHW temperature (already deserialized by register)."""
        temp = self._data.get("dhw_current_temp")
        if temp is None:
            return None
        return float(temp)

    def get_dhw_target_temperature(self) -> float | None:
        """Get DHW target temperature."""
        temp = self._data.get("dhw_target_temp")
        if temp is None:
            return None
        return float(temp)

    def get_dhw_high_demand(self) -> bool | None:
        """Get DHW high demand mode state."""
        value = self._data.get("dhw_high_demand")
        if value is None:
            return None
        return bool(value)

    def get_dhw_boost(self) -> bool | None:
        """Get DHW boost mode state."""
        value = self._data.get("dhw_boost")
        if value is None:
            return None
        return bool(value)

    def get_dhw_antilegionella_temperature(self) -> float | None:
        """Get anti-legionella target temperature from STATUS register."""
        temp = self._data.get("dhw_antilegionella_temp_status")
        if temp is None:
            return None
        return float(temp)

    # DHW control - Setters
    async def set_dhw_power(self, enabled: bool) -> bool:
        """Enable/disable domestic hot water production."""
        return await self.write_value("dhw_power", 1 if enabled else 0)

    async def set_dhw_target_temperature(self, temperature: float) -> bool:
        """Set DHW target temperature (stored in °C)."""
        return await self.write_value("dhw_target_temp", int(temperature))

    async def set_dhw_high_demand(self, enabled: bool) -> bool:
        """Enable/disable DHW high demand mode."""
        return await self.write_value("dhw_high_demand", 1 if enabled else 0)

    async def set_dhw_boost(self, enabled: bool) -> bool:
        """Enable/disable DHW boost mode."""
        return await self.write_value("dhw_boost", 1 if enabled else 0)

    async def start_dhw_antilegionella(self) -> bool:
        """Start anti-legionella treatment cycle."""
        _LOGGER.debug("Starting anti-legionella cycle (writing 1 to register 1030)")
        result = await self.write_value("dhw_antilegionella", 1)
        _LOGGER.debug("Anti-legionella start result: %s", result)
        return result

    async def set_dhw_antilegionella_temperature(self, temperature: float) -> bool:
        """Set anti-legionella target temperature (stored in °C)."""
        _LOGGER.debug("Setting anti-legionella temp to %s°C", temperature)
        result = await self.write_value("dhw_antilegionella_temp", int(temperature))
        _LOGGER.debug("Anti-legionella temp set result: %s", result)
        return result

    # Pool control - Getters
    def get_pool_power(self) -> bool | None:
        """Get pool heating power state."""
        value = self._data.get("pool_power")
        if value is None:
            return None
        return bool(value)

    def get_pool_current_temperature(self) -> float | None:
        """Get current pool temperature (already deserialized by register)."""
        temp = self._data.get("pool_current_temp")
        if temp is None:
            return None
        return float(temp)

    def get_pool_target_temperature(self) -> float | None:
        """Get pool target temperature."""
        temp = self._data.get("pool_target_temp")
        if temp is None:
            return None
        return float(temp)

    # Pool control - Setters
    async def set_pool_power(self, enabled: bool) -> bool:
        """Enable/disable pool heating."""
        return await self.write_value("pool_power", 1 if enabled else 0)

    async def set_pool_target_temperature(self, temperature: float) -> bool:
        """Set pool target temperature."""
        reg = self._register_map.all_registers.get("pool_target_temp")
        if reg and reg.serializer:
            value = reg.serializer(temperature)
        else:
            value = int(temperature)
        return await self.write_value("pool_target_temp", value)
