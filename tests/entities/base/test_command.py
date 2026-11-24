"""A gateway write that fails is reported, whichever entity sent it."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.const import DOMAIN, PRESET_DHW_HIGH_DEMAND
from custom_components.hitachi_yutaki.entities.base.button import (
    HitachiYutakiButton,
    HitachiYutakiButtonEntityDescription,
)
from custom_components.hitachi_yutaki.entities.base.climate import (
    HitachiYutakiClimate,
    HitachiYutakiClimateEntityDescription,
)
from custom_components.hitachi_yutaki.entities.base.command import (
    COMMAND_PARTIALLY_APPLIED,
    WRITE_FAILED,
    CommandStep,
    async_send_command,
)
from custom_components.hitachi_yutaki.entities.base.water_heater import (
    HitachiYutakiWaterHeater,
)
from homeassistant.components.climate import ATTR_HVAC_MODE, HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo


def _coordinator(api_client) -> MagicMock:
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test"
    coordinator.profile.entity_overrides = {}
    coordinator.has_circuit.return_value = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.api_client = api_client
    return coordinator


# --- The shared command path ------------------------------------------------


async def test_all_steps_applied_refreshes_without_error() -> None:
    """A command whose writes all succeed only re-reads the device."""
    coordinator = _coordinator(MagicMock())
    first, second = AsyncMock(return_value=True), AsyncMock(return_value=None)
    await async_send_command(
        coordinator, "climate.x", CommandStep("a", first), CommandStep("b", second)
    )
    first.assert_awaited_once()
    second.assert_awaited_once()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_first_step_refused_is_a_write_failure() -> None:
    """Nothing applied: a plain failure, and later steps are never sent."""
    coordinator = _coordinator(MagicMock())
    second = AsyncMock(return_value=True)
    with pytest.raises(HomeAssistantError) as err:
        await async_send_command(
            coordinator,
            "climate.x",
            CommandStep("a", AsyncMock(return_value=False)),
            CommandStep("b", second),
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == WRITE_FAILED
    assert err.value.translation_placeholders == {"entity": "climate.x", "step": "a"}
    second.assert_not_awaited()
    coordinator.async_request_refresh.assert_awaited_once()


async def test_later_step_refused_reports_what_was_applied() -> None:
    """A half-applied command says which writes already reached the unit."""
    coordinator = _coordinator(MagicMock())
    with pytest.raises(HomeAssistantError) as err:
        await async_send_command(
            coordinator,
            "climate.x",
            CommandStep("a", AsyncMock(return_value=True)),
            CommandStep("b", AsyncMock(return_value=False)),
        )
    assert err.value.translation_key == COMMAND_PARTIALLY_APPLIED
    assert err.value.translation_placeholders == {
        "entity": "climate.x",
        "step": "b",
        "applied": "a",
    }
    coordinator.async_request_refresh.assert_awaited_once()


def test_error_messages_are_translated() -> None:
    """Every key the command path raises has an English message."""
    translations = json.loads(
        (
            Path(__file__).parents[3]
            / "custom_components/hitachi_yutaki/translations/en.json"
        ).read_text()
    )
    for key in (WRITE_FAILED, COMMAND_PARTIALLY_APPLIED):
        message = translations["exceptions"][key]["message"]
        assert "{entity}" in message
        assert "{step}" in message
    assert (
        "{applied}" in translations["exceptions"][COMMAND_PARTIALLY_APPLIED]["message"]
    )


# --- Climate ----------------------------------------------------------------


def _climate(*, multi_circuit: bool = False, **writes: bool) -> HitachiYutakiClimate:
    api = SimpleNamespace(
        supported_unit_modes=("cool", "heat", "auto"),
        can_write=lambda key: True,
        set_circuit_power=AsyncMock(return_value=writes.get("power", True)),
        set_unit_mode=AsyncMock(return_value=writes.get("mode", True)),
        set_circuit_target_temperature=AsyncMock(
            return_value=writes.get("temperature", True)
        ),
        set_circuit_room_temperature=AsyncMock(return_value=writes.get("room", True)),
        set_circuit_eco_mode=AsyncMock(return_value=writes.get("eco", True)),
    )
    climate = HitachiYutakiClimate(
        _coordinator(api),
        HitachiYutakiClimateEntityDescription(key="climate", translation_key="climate"),
        DeviceInfo(identifiers={(DOMAIN, "test")}),
        1,
        multi_circuit=multi_circuit,
    )
    climate.entity_id = "climate.circuit_1"
    return climate


async def test_climate_refused_unit_mode_after_power_is_partial() -> None:
    """Power on applied but mode refused: reported, never silent (root cause #6)."""
    climate = _climate(mode=False)
    with pytest.raises(HomeAssistantError) as err:
        await climate.async_set_hvac_mode(HVACMode.COOL)
    assert err.value.translation_key == COMMAND_PARTIALLY_APPLIED
    assert err.value.translation_placeholders["applied"] == "circuit_power"
    assert err.value.translation_placeholders["step"] == "unit_mode"
    climate.coordinator.async_request_refresh.assert_awaited_once()


async def test_climate_refused_power_skips_unit_mode() -> None:
    """A refused power-on does not go on to change the global mode."""
    climate = _climate(power=False)
    with pytest.raises(HomeAssistantError) as err:
        await climate.async_set_hvac_mode(HVACMode.HEAT)
    assert err.value.translation_key == WRITE_FAILED
    climate.coordinator.api_client.set_unit_mode.assert_not_awaited()


async def test_climate_refused_power_off_raises() -> None:
    """Turning a circuit off that stays on is an error."""
    climate = _climate(power=False)
    with pytest.raises(HomeAssistantError):
        await climate.async_turn_off()


@pytest.mark.parametrize(
    ("method", "kwargs", "write"),
    [
        ("async_set_temperature", {ATTR_TEMPERATURE: 21.0}, "temperature"),
        ("async_set_room_temperature", {ATTR_TEMPERATURE: 19.5}, "room"),
        ("async_set_preset_mode", {"preset_mode": "eco"}, "eco"),
    ],
)
async def test_climate_single_write_refusal_raises(method, kwargs, write) -> None:
    """Every climate command propagates a refused write."""
    climate = _climate(**{write: False})
    with pytest.raises(HomeAssistantError):
        await getattr(climate, method)(**kwargs)


async def test_set_temperature_applies_hvac_mode_first() -> None:
    """``set_temperature`` with ``hvac_mode: off`` turns the circuit off (#45)."""
    climate = _climate()
    api = climate.coordinator.api_client
    order: list[str] = []
    api.set_circuit_power.side_effect = lambda *a: order.append("power") or True
    api.set_circuit_target_temperature.side_effect = lambda *a: (
        order.append("temperature") or True
    )

    await climate.async_set_temperature(
        **{ATTR_TEMPERATURE: 20.0, ATTR_HVAC_MODE: HVACMode.OFF}
    )

    assert order == ["power", "temperature"]
    api.set_circuit_power.assert_awaited_once_with(1, False)
    api.set_circuit_target_temperature.assert_awaited_once_with(1, 20.0)
    api.set_unit_mode.assert_not_awaited()


async def test_set_temperature_with_mode_sets_unit_mode() -> None:
    """A heating mode given with the temperature goes through the mode writes."""
    climate = _climate()
    api = climate.coordinator.api_client
    await climate.async_set_temperature(
        **{ATTR_TEMPERATURE: 22.0, ATTR_HVAC_MODE: HVACMode.HEAT}
    )
    api.set_circuit_power.assert_awaited_once_with(1, True)
    api.set_unit_mode.assert_awaited_once_with(HVACMode.HEAT)
    api.set_circuit_target_temperature.assert_awaited_once_with(1, 22.0)


async def test_set_temperature_mode_refused_keeps_temperature_unsent() -> None:
    """A refused mode stops the command before the temperature write."""
    climate = _climate(power=False)
    api = climate.coordinator.api_client
    with pytest.raises(HomeAssistantError) as err:
        await climate.async_set_temperature(
            **{ATTR_TEMPERATURE: 20.0, ATTR_HVAC_MODE: HVACMode.OFF}
        )
    assert err.value.translation_key == WRITE_FAILED
    api.set_circuit_target_temperature.assert_not_awaited()


async def test_set_temperature_refused_after_mode_is_partial() -> None:
    """Mode applied but temperature refused is reported as partial."""
    climate = _climate(temperature=False)
    with pytest.raises(HomeAssistantError) as err:
        await climate.async_set_temperature(
            **{ATTR_TEMPERATURE: 20.0, ATTR_HVAC_MODE: HVACMode.OFF}
        )
    assert err.value.translation_key == COMMAND_PARTIALLY_APPLIED
    assert err.value.translation_placeholders["step"] == "target_temperature"


async def test_set_hvac_mode_only_via_set_temperature() -> None:
    """``hvac_mode`` alone (no temperature) still applies the mode."""
    climate = _climate()
    api = climate.coordinator.api_client
    await climate.async_set_temperature(**{ATTR_HVAC_MODE: HVACMode.OFF})
    api.set_circuit_power.assert_awaited_once_with(1, False)
    api.set_circuit_target_temperature.assert_not_awaited()


# --- Water heater -------------------------------------------------------------


def _water_heater(*, dhw_on: bool = True, **writes: bool) -> HitachiYutakiWaterHeater:
    api = MagicMock()
    api.can_write.return_value = True
    api.get_dhw_power.return_value = dhw_on
    api.set_dhw_power = AsyncMock(return_value=writes.get("power", True))
    api.set_dhw_high_demand = AsyncMock(return_value=writes.get("high_demand", True))
    api.set_dhw_target_temperature = AsyncMock(
        return_value=writes.get("temperature", True)
    )
    entity = HitachiYutakiWaterHeater.__new__(HitachiYutakiWaterHeater)
    entity.coordinator = _coordinator(api)
    entity.entity_id = "water_heater.dhw"
    return entity


async def test_water_heater_high_demand_refused_after_power_is_partial() -> None:
    """DHW switched on but high demand refused is reported as partial."""
    entity = _water_heater(dhw_on=False, high_demand=False)
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_operation_mode(PRESET_DHW_HIGH_DEMAND)
    assert err.value.translation_key == COMMAND_PARTIALLY_APPLIED
    assert err.value.translation_placeholders["applied"] == "dhw_power"


@pytest.mark.parametrize(
    ("method", "kwargs", "write"),
    [
        ("async_turn_on", {}, "power"),
        ("async_turn_off", {}, "power"),
        ("async_set_temperature", {ATTR_TEMPERATURE: 50}, "temperature"),
    ],
)
async def test_water_heater_refusal_raises(method, kwargs, write) -> None:
    """Every water heater command propagates a refused write."""
    entity = _water_heater(**{write: False})
    with pytest.raises(HomeAssistantError):
        await getattr(entity, method)(**kwargs)


# --- Button -------------------------------------------------------------------


def _button(result) -> HitachiYutakiButton:
    coordinator = _coordinator(MagicMock())
    button = HitachiYutakiButton(
        coordinator,
        HitachiYutakiButtonEntityDescription(
            key="antilegionella",
            translation_key="antilegionella",
            action_fn=AsyncMock(return_value=result),
        ),
        DeviceInfo(identifiers={(DOMAIN, "test")}),
    )
    button.entity_id = "button.antilegionella"
    return button


async def test_button_refused_write_raises() -> None:
    """A refused anti-legionella start is no longer reported as pressed."""
    button = _button(False)
    with pytest.raises(HomeAssistantError):
        await button.async_press()
    button.coordinator.async_request_refresh.assert_awaited_once()


async def test_button_local_action_without_status_succeeds() -> None:
    """An action that is not a gateway write (returns None) is not a failure."""
    button = _button(None)
    await button.async_press()
    button.coordinator.async_request_refresh.assert_awaited_once()
