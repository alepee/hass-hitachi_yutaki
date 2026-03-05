"""Global test fixtures for Hitachi Yutaki integration."""

import pytest
from pytest_homeassistant_custom_component.typing import RecorderInstanceContextManager


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
