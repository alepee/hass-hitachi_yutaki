"""Tests for the climate entity hvac_action resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.entities.base.climate import (
    HitachiYutakiClimate,
    HitachiYutakiClimateEntityDescription,
)
from homeassistant.components.climate import PRESET_ECO, HVACAction, HVACMode
from homeassistant.helpers.entity import DeviceInfo


def _make_climate(
    *,
    unit_mode: HVACMode | None = HVACMode.AUTO,
    operation_state: str | None = None,
    circuit_power: bool = True,
    is_defrosting: bool = False,
    is_compressor_running: bool = True,
    multi_circuit: bool = False,
) -> HitachiYutakiClimate:
    """Build a climate entity with a mocked coordinator/api_client.

    Bypasses ``__init__`` to avoid the full HA entity setup; only the
    attributes used by the ``hvac_action`` property are wired.
    """
    climate = HitachiYutakiClimate.__new__(HitachiYutakiClimate)

    api_client = MagicMock()
    api_client.get_circuit_power.return_value = circuit_power
    api_client.get_unit_mode.return_value = unit_mode
    api_client.get_operation_state.return_value = operation_state
    api_client.is_defrosting = is_defrosting
    api_client.is_compressor_running = is_compressor_running

    coordinator = MagicMock()
    coordinator.data = {"some": "data"}
    coordinator.api_client = api_client

    climate.coordinator = coordinator
    climate._circuit_id = 1
    climate._multi_circuit = multi_circuit

    return climate


class TestHvacAction:
    """Tests for the hvac_action property."""

    def test_auto_running_heating(self):
        """AUTO + heat operation state resolves to HEATING."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_heat_thermo_on",
        )
        assert climate.hvac_action == HVACAction.HEATING

    def test_auto_running_cooling(self):
        """AUTO + cool operation state resolves to COOLING."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_cool_thermo_on",
        )
        assert climate.hvac_action == HVACAction.COOLING

    def test_auto_indeterminate_operation_state(self):
        """AUTO + unknown operation state returns None (no signal)."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state=None,
        )
        assert climate.hvac_action is None

    def test_explicit_heat_unchanged(self):
        """Explicit HEAT mode still resolves to HEATING."""
        climate = _make_climate(unit_mode=HVACMode.HEAT)
        assert climate.hvac_action == HVACAction.HEATING

    def test_explicit_cool_unchanged(self):
        """Explicit COOL mode still resolves to COOLING."""
        climate = _make_climate(unit_mode=HVACMode.COOL)
        assert climate.hvac_action == HVACAction.COOLING

    def test_off_returns_off(self):
        """Powered-off circuit returns OFF."""
        climate = _make_climate(circuit_power=False)
        assert climate.hvac_action == HVACAction.OFF

    def test_defrosting_returns_defrosting(self):
        """Defrosting unit returns DEFROSTING regardless of mode."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            operation_state="operation_state_heat_thermo_on",
            is_defrosting=True,
        )
        assert climate.hvac_action == HVACAction.DEFROSTING

    def test_idle_when_compressor_off(self):
        """Compressor not running returns IDLE."""
        climate = _make_climate(
            unit_mode=HVACMode.AUTO,
            is_compressor_running=False,
        )
        assert climate.hvac_action == HVACAction.IDLE

    def test_no_data_returns_none(self):
        """No coordinator data returns None (entity not OFF)."""
        climate = _make_climate(unit_mode=HVACMode.HEAT)
        climate.coordinator.data = None
        assert climate.hvac_action is None


@pytest.mark.parametrize("unit_mode", [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO])
@pytest.mark.parametrize("multi_circuit", [False, True])
@pytest.mark.parametrize(
    "operation", ["dhw_on", "pool_on", "heat_thermo_off", "cool_demand_off", "off"]
)
def test_other_loads_and_inactive_states_are_idle(unit_mode, multi_circuit, operation):
    """A running compressor does not imply this circuit is heating or cooling."""
    climate = _make_climate(
        unit_mode=unit_mode,
        multi_circuit=multi_circuit,
        operation_state=f"operation_state_{operation}",
    )
    assert climate.hvac_action == HVACAction.IDLE


@pytest.mark.parametrize("multi_circuit", [False, True])
def test_reported_direction_overrides_selected_mode(multi_circuit):
    """Actual cooling takes precedence over a global heat command."""
    climate = _make_climate(
        unit_mode=HVACMode.HEAT,
        multi_circuit=multi_circuit,
        operation_state="operation_state_cool_thermo_on",
    )
    assert climate.hvac_action == HVACAction.COOLING


def _initialized_climate(
    *,
    multi_circuit=False,
    modes=("cool", "heat", "auto"),
    writable_eco=True,
    heating=True,
    cooling=True,
):
    """Build an entity against an API contract with no raw register map."""
    coordinator = MagicMock()
    coordinator.profile.entity_overrides = {}
    coordinator.config_entry.entry_id = "test"
    coordinator.has_circuit.side_effect = lambda circuit, mode: (
        heating if mode == "heating" else cooling
    )
    coordinator.async_request_refresh = AsyncMock()
    coordinator.api_client = SimpleNamespace(
        supported_unit_modes=modes,
        can_write=lambda key: writable_eco and key == "circuit1_eco_mode",
        set_circuit_power=AsyncMock(),
        set_unit_mode=AsyncMock(),
    )
    return HitachiYutakiClimate(
        coordinator,
        HitachiYutakiClimateEntityDescription(key="climate", translation_key="climate"),
        DeviceInfo(identifiers={("hitachi_yutaki", "test")}),
        1,
        multi_circuit=multi_circuit,
    )


@pytest.mark.parametrize(
    ("modes", "heating", "cooling", "expected"),
    [
        (
            ("cool", "heat", "auto"),
            True,
            True,
            [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO],
        ),
        (("cool", "heat"), True, True, [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]),
        (("cool", "heat", "auto"), True, False, [HVACMode.OFF, HVACMode.HEAT]),
        (("cool", "heat", "auto"), False, True, [HVACMode.OFF, HVACMode.COOL]),
        (("heat",), True, True, [HVACMode.OFF, HVACMode.HEAT]),
    ],
)
def test_single_circuit_modes_use_api_contract(modes, heating, cooling, expected):
    """Available commands honor both configured modes and API write support."""
    climate = _initialized_climate(modes=modes, heating=heating, cooling=cooling)
    assert climate.hvac_modes == expected


@pytest.mark.parametrize("writable", [False, True])
def test_eco_preset_requires_writable_key(writable):
    """A missing or read-only ECO key cannot advertise a writable preset."""
    climate = _initialized_climate(writable_eco=writable)
    assert (PRESET_ECO in climate.preset_modes) is writable


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "requested",
    [HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
)
async def test_multi_circuit_never_writes_global_mode(requested):
    """Even direct heat/cool calls preserve the other circuit's global mode."""
    climate = _initialized_climate(multi_circuit=True)
    assert climate.hvac_modes == [HVACMode.OFF, HVACMode.HEAT_COOL]
    await climate.async_set_hvac_mode(requested)
    climate.coordinator.api_client.set_unit_mode.assert_not_awaited()
    climate.coordinator.api_client.set_circuit_power.assert_awaited_once_with(
        1, requested != HVACMode.OFF
    )
    climate.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO])
async def test_single_circuit_writes_global_mode(requested):
    """The single circuit still controls unit mode and its own power."""
    climate = _initialized_climate()
    await climate.async_set_hvac_mode(requested)
    climate.coordinator.api_client.set_circuit_power.assert_awaited_once_with(1, True)
    climate.coordinator.api_client.set_unit_mode.assert_awaited_once_with(requested)


@pytest.mark.parametrize(
    ("unit_mode", "expected"),
    [
        (HVACMode.AUTO, None),
        (HVACMode.HEAT, HVACAction.HEATING),
        (HVACMode.COOL, HVACAction.COOLING),
    ],
)
def test_unknown_operation_code_uses_missing_state_fallback(unit_mode, expected):
    """An unmapped gateway code does not invent an actual operating direction."""
    climate = _make_climate(
        unit_mode=unit_mode, operation_state="operation_state_unknown"
    )
    assert climate.hvac_action == expected
