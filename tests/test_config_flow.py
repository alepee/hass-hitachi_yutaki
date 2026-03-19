"""Tests for Hitachi Yutaki config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.const import (
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    DEFAULT_DEVICE_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_SUPPLY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Standard test data matching the config flow schemas
GATEWAY_USER_INPUT = {"gateway_type": "modbus_atw_mbs_02"}

GATEWAY_VARIANT_INPUT = {"gateway_variant": "gen2"}

GATEWAY_CONFIG_INPUT = {
    "name": DEFAULT_NAME,
    CONF_MODBUS_HOST: DEFAULT_HOST,
    CONF_MODBUS_PORT: DEFAULT_PORT,
    CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
    "scan_interval": DEFAULT_SCAN_INTERVAL,
}

PROFILE_INPUT = {"profile": "yutaki_s"}

POWER_INPUT = {"power_supply": DEFAULT_POWER_SUPPLY}


def _mock_api_client() -> MagicMock:
    """Create a mock API client."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.connected = True
    client.read_values = AsyncMock()
    client.read_value = AsyncMock(return_value=0)
    client.decode_config = MagicMock(return_value={})
    client.get_model_key = AsyncMock(return_value="yutaki_s")
    client.async_get_unique_id = AsyncMock(return_value="ABCD1234")
    client.register_map = MagicMock()
    client.register_map.base_keys = ["system_config", "system_state"]
    client.register_map.gateway_keys = ["system_state"]
    client.is_defrosting = False
    return client


def _mock_gateway_info(client: MagicMock) -> MagicMock:
    """Create a mock GATEWAY_INFO dict-like object."""
    gateway_info = MagicMock()
    gateway_info.__getitem__ = MagicMock(
        return_value=MagicMock(client_class=MagicMock(return_value=client))
    )
    gateway_info.keys = MagicMock(return_value=["modbus_atw_mbs_02"])
    return gateway_info


def _mock_profiles() -> MagicMock:
    """Create mock PROFILES."""
    profile = MagicMock()
    profile.detect = MagicMock(return_value=True)
    profiles = MagicMock()
    profiles.items = MagicMock(return_value=[("yutaki_s", profile)])
    profiles.keys = MagicMock(return_value=["yutaki_s"])
    profiles.__getitem__ = MagicMock(return_value=profile)
    return profiles


async def _advance_to_gateway_variant(hass: HomeAssistant) -> dict:
    """Advance the flow through user step to gateway_variant."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], GATEWAY_USER_INPUT
    )
    return result


async def _advance_to_gateway_config(hass: HomeAssistant) -> dict:
    """Advance the flow through user and variant steps to gateway_config."""
    result = await _advance_to_gateway_variant(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], GATEWAY_VARIANT_INPUT
    )
    return result


async def _advance_to_profile(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_gw_info: MagicMock,
    mock_profiles: MagicMock,
) -> dict:
    """Advance the flow through gateway_config to profile step."""
    result = await _advance_to_gateway_config(hass)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
        patch("custom_components.hitachi_yutaki.config_flow.PROFILES", mock_profiles),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )
    return result


async def _advance_to_power(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_gw_info: MagicMock,
    mock_profiles: MagicMock,
) -> dict:
    """Advance the flow through profile to power step."""
    result = await _advance_to_profile(hass, mock_client, mock_gw_info, mock_profiles)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PROFILE_INPUT
    )
    return result


# ── User step tests ──


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the gateway selection form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_advances_to_gateway_variant(hass: HomeAssistant) -> None:
    """Test gateway selection advances to gateway_variant step for ATW-MBS-02."""
    result = await _advance_to_gateway_variant(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_variant"


# ── Gateway variant step tests ──


async def test_gateway_variant_advances_to_gateway_config(
    hass: HomeAssistant,
) -> None:
    """Test gateway variant selection advances to gateway_config step."""
    result = await _advance_to_gateway_config(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "gateway_config"


# ── Gateway config tests ──


async def test_gateway_config_connection_failure(hass: HomeAssistant) -> None:
    """Test that connection failure shows error on gateway_config step."""
    result = await _advance_to_gateway_config(hass)

    mock_client = _mock_api_client()
    mock_client.connect = AsyncMock(return_value=False)
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_gateway_config_success_advances_to_profile(
    hass: HomeAssistant,
) -> None:
    """Test successful connection advances to profile selection."""
    result = await _advance_to_gateway_config(hass)

    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
        patch("custom_components.hitachi_yutaki.config_flow.PROFILES", mock_profs),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profile"


# ── Profile step tests ──


async def test_profile_step_advances_to_power(hass: HomeAssistant) -> None:
    """Test profile selection advances to power configuration."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_profile(hass, mock_client, mock_gw_info, mock_profs)
    assert result["step_id"] == "profile"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PROFILE_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "power"


# ── Full flow + validation tests ──


async def test_full_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test the complete flow from user to entry creation."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)
    assert result["step_id"] == "power"

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"]["gateway_type"] == "modbus_atw_mbs_02"
    assert result["data"]["gateway_variant"] == "gen2"
    assert result["data"]["profile"] == "yutaki_s"
    assert result["data"]["power_supply"] == DEFAULT_POWER_SUPPLY


async def test_validate_connection_system_initializing(
    hass: HomeAssistant,
) -> None:
    """Test system_state=2 returns system_initializing error."""
    mock_client = _mock_api_client()
    mock_client.read_value = AsyncMock(return_value=2)
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "system_initializing"}


async def test_validate_connection_desync(hass: HomeAssistant) -> None:
    """Test system_state=1 returns desync_error."""
    mock_client = _mock_api_client()
    mock_client.read_value = AsyncMock(return_value=1)
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "desync_error"}


async def test_validate_connection_invalid_slave(hass: HomeAssistant) -> None:
    """Test no model_key returns invalid_slave error."""
    mock_client = _mock_api_client()
    mock_client.get_model_key = AsyncMock(return_value=None)
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_slave"}


async def test_validate_connection_duplicate_entry_abort(
    hass: HomeAssistant,
) -> None:
    """Test that duplicate unique_id aborts flow."""
    # Create an existing entry with the same unique_id
    existing_entry = MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title="Existing",
        data={},
        unique_id=f"{DOMAIN}_ABCD1234",
    )
    existing_entry.add_to_hass(hass)

    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        patch(
            "custom_components.hitachi_yutaki.config_flow.GATEWAY_INFO", mock_gw_info
        ),
        patch("custom_components.hitachi_yutaki.config_flow.create_register_map"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ── Options flow tests ──


async def test_options_flow_init_shows_form(hass: HomeAssistant) -> None:
    """Test options flow shows gateway selection."""
    entry = MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            "gateway_type": "modbus_atw_mbs_02",
            "gateway_variant": "gen2",
            CONF_MODBUS_HOST: DEFAULT_HOST,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_full_update(hass: HomeAssistant) -> None:
    """Test full options flow updates entry data and triggers reload."""
    entry = MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            "gateway_type": "modbus_atw_mbs_02",
            "gateway_variant": "gen2",
            "name": DEFAULT_NAME,
            CONF_MODBUS_HOST: DEFAULT_HOST,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
    )
    entry.add_to_hass(hass)

    # Step 1: init (gateway selection)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"gateway_type": "modbus_atw_mbs_02"},
    )
    assert result["step_id"] == "gateway_variant"

    # Step 1b: gateway variant
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"gateway_variant": "gen1"},
    )
    assert result["step_id"] == "connection"

    # Step 2: connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MODBUS_HOST: "192.168.1.100",
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
        },
    )
    assert result["step_id"] == "profile"

    # Step 3: profile
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile": "yutaki_s_combi"},
    )
    assert result["step_id"] == "sensors"

    # Step 4: sensors
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"power_supply": "three"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify data was updated
    assert entry.data[CONF_MODBUS_HOST] == "192.168.1.100"
    assert entry.data["profile"] == "yutaki_s_combi"
    assert entry.data["power_supply"] == "three"
    assert entry.data["gateway_variant"] == "gen1"
