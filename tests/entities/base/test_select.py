"""Operating mode selects consume only the public API capabilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hitachi_yutaki.api.base import HitachiApiClient
from custom_components.hitachi_yutaki.entities.control_unit.selects import (
    build_control_unit_selects,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


def _coordinator(modes: tuple[str, ...], cooling: bool = True) -> MagicMock:
    client = MagicMock(spec_set=HitachiApiClient)
    client.can_write.return_value = True
    client.supported_unit_modes = modes
    client.set_unit_mode = AsyncMock(return_value=True)
    coordinator = MagicMock(
        api_client=client, last_update_success=True, data={"unit_mode": 1}
    )
    coordinator.config_entry.entry_id = "test"
    coordinator.has_circuit.return_value = cooling
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.parametrize(
    ("modes", "cooling", "expected"),
    [
        (("cool", "heat", "auto"), True, ["cool", "heat", "auto"]),
        (("cool", "heat", "auto"), False, ["heat", "auto"]),
        (("cool", "heat"), True, ["cool", "heat"]),
        (("cool", "heat"), False, ["heat"]),
    ],
)
def test_modes_intersect_gateway_and_profile(modes, cooling, expected) -> None:
    """HC-A never offers Auto, while ATW keeps existing options and IDs."""
    coordinator = _coordinator(modes, cooling)
    entities = build_control_unit_selects(coordinator, "test")
    assert len(entities) == 1
    assert entities[0].options == expected
    assert (
        entities[0].unique_id == f"test_operation_mode_{'full' if cooling else 'heat'}"
    )
    coordinator.api_client.get_unit_mode.return_value = "heat"
    assert entities[0].current_option == "heat"


async def test_unsupported_auto_does_not_write_or_refresh() -> None:
    """Even a direct service call cannot request unsupported Auto."""
    coordinator = _coordinator(("cool", "heat"))
    entity = build_control_unit_selects(coordinator, "test")[0]
    with pytest.raises(ServiceValidationError, match="Unsupported option"):
        await entity.async_select_option("auto")
    coordinator.api_client.set_unit_mode.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


async def test_failed_write_is_a_service_error() -> None:
    """A false API result is observable instead of appearing successful."""
    coordinator = _coordinator(("cool", "heat"))
    coordinator.api_client.set_unit_mode.return_value = False
    entity = build_control_unit_selects(coordinator, "test")[0]
    with pytest.raises(HomeAssistantError, match="Failed to select"):
        await entity.async_select_option("heat")
    coordinator.api_client.set_unit_mode.assert_awaited_once_with("heat")
    coordinator.async_request_refresh.assert_not_awaited()


async def test_successful_write_refreshes_state() -> None:
    """Supported commands retain their normal write and refresh behavior."""
    coordinator = _coordinator(("cool", "heat"))
    entity = build_control_unit_selects(coordinator, "test")[0]
    await entity.async_select_option("cool")
    coordinator.api_client.set_unit_mode.assert_awaited_once_with("cool")
    coordinator.async_request_refresh.assert_awaited_once()


def test_readonly_unit_mode_does_not_create_select() -> None:
    """A gateway without writable global mode gets no control entity."""
    coordinator = _coordinator(())
    coordinator.api_client.can_write.return_value = False
    assert build_control_unit_selects(coordinator, "test") == []
