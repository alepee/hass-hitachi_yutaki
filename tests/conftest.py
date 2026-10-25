"""Global test fixtures for Hitachi Yutaki integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.hitachi_yutaki.const import DOMAIN
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    # Missing from the phac releases of the oldest supported HA.
    from pytest_homeassistant_custom_component.typing import (
        RecorderInstanceContextManager,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Force recorder_db_url to resolve before hass fixture.

    Required because our integration declares recorder as a dependency.
    """


@pytest.fixture(autouse=True)
async def auto_setup_recorder(recorder_mock):
    """Set up in-memory recorder for all tests."""
    return


@pytest.fixture
async def unload_entries(hass: HomeAssistant):
    """Run the unload callbacks of entries set up by calling async_setup_entry.

    Such entries never reach the LOADED state, so nothing unloads them and
    their timers (telemetry flush, fleet ping) would outlive the test.
    """
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        await entry._async_process_on_unload(hass)
