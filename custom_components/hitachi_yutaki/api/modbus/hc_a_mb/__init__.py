"""Modbus client for the HC-A(16/64)MB gateway.

An HC-A(16/64)MB gateway hosts several H-LINK units, each in a slot of its unit
table. The slot keys the unit's indoor register block, but it is not a stable
identity (see ``unit_table``), so this client binds to the unit's ``(Ou, Iu)``
pair and follows it to its current slot.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ....const import (
    CONF_INDOOR_ADDRESS,
    CONF_OUTDOOR_CYCLE,
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
    get_pymodbus_device_param,
)
from ...base import UnitBinding, UnitBindingStatus
from .. import ModbusApiClient
from ..registers.hc_a_mb import HcAMbRegisterMap
from .unit_table import (
    REASON_NOT_SETTLED,
    UNIT_TABLE_SLOTS,
    UNIT_TABLE_STRIDE,
    UnitSlot,
    parse_unit_table,
    resolve_slot,
    slot_address,
)

_LOGGER = logging.getLogger(__name__)


class HcAMbApiClient(ModbusApiClient):
    """Modbus client for the HC-A(16/64)MB gateway."""

    _register_map: HcAMbRegisterMap

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the client; the unit identity is set by async_bind_unit."""
        super().__init__(*args, **kwargs)
        self._unit_identity: tuple[int, int] | None = None

    async def async_read_unit_table(
        self, first_slot: int = 0, slots: int = UNIT_TABLE_SLOTS
    ) -> list[UnitSlot] | None:
        """Read slots of the gateway unit table (#353, #476).

        One function code 04 request at ``200 + first_slot * 4``.

        Args:
            first_slot: Index of the first slot to read.
            slots: Number of slots to read.

        Returns:
            The decoded slots, or None if the table cannot be read.

        """
        device_param = get_pymodbus_device_param()
        address = slot_address(first_slot)
        count = slots * UNIT_TABLE_STRIDE

        try:
            result = await self._hass.async_add_executor_job(
                lambda: self._client.read_input_registers(
                    address=address,
                    count=count,
                    **{device_param: self._slave},
                )
            )
        except (ModbusException, ConnectionError, OSError) as exc:
            _LOGGER.warning(
                "Communication error reading unit table (registers %d-%d): %s",
                address,
                address + count - 1,
                exc,
            )
            return None

        if result.isError() or len(result.registers or []) < count:
            _LOGGER.warning(
                "Failed to read unit table (registers %d-%d): %s",
                address,
                address + count - 1,
                result,
            )
            return None

        return parse_unit_table(list(result.registers[:count]), first_slot)

    async def async_bind_unit(self, entry_data: Mapping[str, Any]) -> UnitBinding:
        """Locate the entry's unit in the unit table and rebind to its slot.

        The entry stores the unit's ``(Ou, Iu)`` pair; its slot is looked up in
        the table. Older entries self-heal: with only ``Ou`` (#353) the unit is
        matched on its cycle, with neither it is the one in the stored slot.
        Never falls back to a slot holding another unit. An unreadable table
        leaves the client on the stored slot, still verified against the
        stored pair at runtime.
        """
        stored_slot = entry_data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
        outdoor_cycle = entry_data.get(CONF_OUTDOOR_CYCLE)
        indoor_address = entry_data.get(CONF_INDOOR_ADDRESS)
        # The stored pair is the reference for async_verify_unit even when the
        # table cannot be read now: the client then stays on the stored slot,
        # and the runtime check must still catch a unit that moved.
        if outdoor_cycle is not None and indoor_address is not None:
            self._unit_identity = (outdoor_cycle, indoor_address)

        table = None
        try:
            if self.connected or await self.connect():
                table = await self.async_read_unit_table()
        except Exception as exc:  # noqa: BLE001 - an unreadable table is not fatal
            _LOGGER.debug("Error reading the gateway unit table: %s", exc)
        if table is None:
            _LOGGER.debug("Unit table unavailable, keeping slot %d", stored_slot)
            return UnitBinding(UnitBindingStatus.UNVERIFIED)

        resolution = resolve_slot(table, stored_slot, outdoor_cycle, indoor_address)
        if resolution.reason == REASON_NOT_SETTLED:
            return UnitBinding(UnitBindingStatus.SETTLING)

        unit = resolution.slot
        if unit is None:
            if outdoor_cycle is None:
                # Pre-#353 entry on an empty slot: nothing to compare against,
                # keep the previous best-effort behaviour.
                return UnitBinding(UnitBindingStatus.UNVERIFIED)
            return UnitBinding(
                UnitBindingStatus.MISSING,
                placeholders={
                    "outdoor_cycle": str(outdoor_cycle),
                    "indoor_address": str(indoor_address),
                },
            )

        if unit.slot != stored_slot and outdoor_cycle is not None:
            _LOGGER.warning(
                "Unit (Ou=%d, Iu=%d) moved from slot %d to slot %d in the gateway "
                "unit table, following it (#476)",
                unit.outdoor_cycle,
                unit.indoor_address,
                stored_slot,
                unit.slot,
            )
        self._register_map = HcAMbRegisterMap(
            unit_id=unit.slot, outdoor_cycle=unit.outdoor_cycle
        )
        self._unit_identity = unit.identity
        return UnitBinding(
            UnitBindingStatus.BOUND,
            updates={
                CONF_UNIT_ID: unit.slot,
                CONF_OUTDOOR_CYCLE: unit.outdoor_cycle,
                CONF_INDOOR_ADDRESS: unit.indoor_address,
            },
            placeholders={
                "outdoor_cycle": str(unit.outdoor_cycle),
                "indoor_address": str(unit.indoor_address),
            },
        )

    async def async_verify_unit(self) -> bool | None:
        """Return whether the bound slot still holds the bound unit (#476).

        A gateway reboot while Home Assistant runs re-enumerates the bus, and a
        unit missing at that moment shifts the others to new slots. One read of
        the bound slot's descriptor tells whether it still holds this unit.
        """
        if self._unit_identity is None:
            return True
        slot = self._register_map.unit_id
        slots = await self.async_read_unit_table(slot, 1)
        if not slots:
            return None
        if slots[0].is_valid and slots[0].identity == self._unit_identity:
            return True
        _LOGGER.warning(
            "Slot %d of the gateway unit table no longer holds unit "
            "(Ou=%d, Iu=%d) (#476)",
            slot,
            *self._unit_identity,
        )
        return False
