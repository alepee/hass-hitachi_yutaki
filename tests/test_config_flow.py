"""Tests for Hitachi Yutaki config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusException
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hitachi_yutaki.api.base import HitachiApiClient, ReadResult
from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)
from custom_components.hitachi_yutaki.config_flow import (
    SECTION_PREVENTIVE_MAINTENANCE,
    HitachiYutakiConfigFlow,
)
from custom_components.hitachi_yutaki.const import (
    CONF_CYCLING_DETECTION,
    CONF_ENERGY_ENTITY,
    CONF_MODBUS_DEVICE_ID,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_POWER_ENTITY,
    CONF_REFRIGERANT_DETECTION,
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


@pytest.fixture
def mock_setup_entry():
    """Keep a created entry from setting up, which would open a Modbus socket."""
    with patch(
        "custom_components.hitachi_yutaki.async_setup_entry", return_value=True
    ) as mock:
        yield mock


def _mock_api_client() -> MagicMock:
    """Create a mock API client."""
    client = MagicMock(spec_set=HitachiApiClient)
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.connected = True
    client.read_values = AsyncMock(return_value=ReadResult.SUCCESS)
    client.read_value = AsyncMock(return_value=0)
    client.decode_config = MagicMock(return_value={})
    client.get_model_key = AsyncMock(return_value="yutaki_s")
    client.async_get_unique_id = AsyncMock(return_value="ABCD1234")
    client.base_keys = ["system_config", "system_state"]
    client.gateway_keys = ["system_state"]
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


# Patch targets for provider modules (where the symbols are used)
_PATCH_ATW_GW_INFO = (
    "custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02.GATEWAY_INFO"
)
_PATCH_ATW_CREATE_RM = "custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02.create_register_map"
_PATCH_ATW_PROFILES = (
    "custom_components.hitachi_yutaki.api.config_providers.atw_mbs_02.PROFILES"
)
_PATCH_CF_CREATE_CLIENT = (
    "custom_components.hitachi_yutaki.config_flow.create_api_client"
)


def _patch_cf_client(gateway_info: MagicMock):
    """Patch the flow's client factory to hand out the mocked client."""
    return patch(
        _PATCH_CF_CREATE_CLIENT,
        side_effect=lambda _hass, config: gateway_info[
            config["gateway_type"]
        ].client_class(),
    )


async def _advance_to_connection(hass: HomeAssistant) -> dict:
    """Advance the flow through user step to atw_mbs_02_connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], GATEWAY_USER_INPUT
    )
    return result


async def _advance_to_variant(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_gw_info: MagicMock,
) -> dict:
    """Advance the flow through connection to variant step."""
    result = await _advance_to_connection(hass)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )
    return result


async def _advance_to_profile(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_gw_info: MagicMock,
    mock_profiles: MagicMock,
) -> dict:
    """Advance the flow through variant to profile step."""
    result = await _advance_to_variant(hass, mock_client, mock_gw_info)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
        patch(_PATCH_ATW_PROFILES, mock_profiles),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_VARIANT_INPUT
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


async def test_user_step_advances_to_connection(hass: HomeAssistant) -> None:
    """Test gateway selection advances to provider's first step."""
    result = await _advance_to_connection(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "atw_mbs_02_connection"


# ── Connection step tests ──


async def test_connection_failure(hass: HomeAssistant) -> None:
    """Test that connection failure shows error on connection step."""
    result = await _advance_to_connection(hass)

    mock_client = _mock_api_client()
    mock_client.connect = AsyncMock(return_value=False)
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


def _suggested_values(schema) -> dict:
    """Extract `suggested_value` for each key in a voluptuous Schema.

    HA stores user-typed defaults in `key.description["suggested_value"]`
    after `FlowHandler.add_suggested_values_to_schema()` is applied.
    """
    out: dict = {}
    for key in schema.schema:
        desc = getattr(key, "description", None)
        if isinstance(desc, dict) and "suggested_value" in desc:
            out[key.schema] = desc["suggested_value"]
    return out


async def test_connection_failure_preserves_user_input(hass: HomeAssistant) -> None:
    """On connection failure, the form re-renders with the user-typed values.

    Regression test for #304: host/port/slave/name typed by the user must
    survive a validation error so they don't have to re-type on every retry.
    """
    result = await _advance_to_connection(hass)

    mock_client = _mock_api_client()
    mock_client.connect = AsyncMock(return_value=False)
    mock_gw_info = _mock_gateway_info(mock_client)

    typed = {
        "name": "My Yutaki",
        CONF_MODBUS_HOST: "10.20.30.40",
        CONF_MODBUS_PORT: 1502,
        CONF_MODBUS_DEVICE_ID: 7,
        "scan_interval": DEFAULT_SCAN_INTERVAL,
    }

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], typed
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    suggested = _suggested_values(result["data_schema"])
    assert suggested.get("name") == "My Yutaki"
    assert suggested.get(CONF_MODBUS_HOST) == "10.20.30.40"
    assert suggested.get(CONF_MODBUS_PORT) == 1502
    assert suggested.get(CONF_MODBUS_DEVICE_ID) == 7


async def test_options_flow_connection_failure_preserves_user_input(
    hass: HomeAssistant,
) -> None:
    """Options flow: connection failure preserves user-typed values (#304)."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"gateway_type": "modbus_atw_mbs_02"},
    )
    assert result["step_id"] == "atw_mbs_02_connection"

    mock_client = _mock_api_client()
    mock_client.connect = AsyncMock(return_value=False)
    mock_gw_info = _mock_gateway_info(mock_client)

    typed = {
        "name": "Renamed Yutaki",
        CONF_MODBUS_HOST: "10.20.30.40",
        CONF_MODBUS_PORT: 1502,
        CONF_MODBUS_DEVICE_ID: 9,
        "scan_interval": DEFAULT_SCAN_INTERVAL,
    }

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], typed
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    suggested = _suggested_values(result["data_schema"])
    assert suggested.get("name") == "Renamed Yutaki"
    assert suggested.get(CONF_MODBUS_HOST) == "10.20.30.40"
    assert suggested.get(CONF_MODBUS_PORT) == 1502
    assert suggested.get(CONF_MODBUS_DEVICE_ID) == 9


async def test_connection_success_advances_to_variant(
    hass: HomeAssistant,
) -> None:
    """Test successful connection advances to variant step for ATW-MBS-02."""
    result = await _advance_to_connection(hass)

    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_CONFIG_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "atw_mbs_02_variant"


# ── Variant step tests ──


async def test_variant_advances_to_profile(
    hass: HomeAssistant,
) -> None:
    """Test variant selection advances to profile step."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_variant(hass, mock_client, mock_gw_info)
    assert result["step_id"] == "atw_mbs_02_variant"

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
        patch(_PATCH_ATW_PROFILES, mock_profs),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], GATEWAY_VARIANT_INPUT
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


async def test_full_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the complete flow from user to entry creation."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)
    assert result["step_id"] == "power"

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    # yutaki_s exposes extended compressor sensors, so the "Advanced features
    # (beta)" panel (refrigerant consent) is the last step before entry creation.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced_features"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: True}},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"]["gateway_type"] == "modbus_atw_mbs_02"
    assert result["data"]["gateway_variant"] == "gen2"
    assert result["data"]["profile"] == "yutaki_s"
    assert result["data"]["power_supply"] == DEFAULT_POWER_SUPPLY
    assert result["options"][CONF_REFRIGERANT_DETECTION] is True


async def test_full_flow_hides_refrigerant_toggle_when_unsupported(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """A profile without extended sensors still gets the panel, minus that toggle.

    Short-cycling detection applies to every profile, so the panel is shown to
    all of them; only the refrigerant toggle is capability-gated.
    """
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    # Advance to the profile step, then select the DHW-only Yutampo R32.
    result = await _advance_to_profile(hass, mock_client, mock_gw_info, mock_profs)
    assert result["step_id"] == "profile"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"profile": "yutampo_r32"}
    )
    assert result["step_id"] == "power"

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced_features"

    section_schema = result["data_schema"].schema[SECTION_PREVENTIVE_MAINTENANCE]
    keys = {str(key) for key in section_schema.schema.schema}
    assert CONF_REFRIGERANT_DETECTION not in keys
    assert CONF_CYCLING_DETECTION in keys

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_CYCLING_DETECTION: True}},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["profile"] == "yutampo_r32"
    assert result["options"][CONF_REFRIGERANT_DETECTION] is False
    assert result["options"][CONF_CYCLING_DETECTION] is True


async def test_validate_connection_system_initializing(
    hass: HomeAssistant,
) -> None:
    """A deserialized initializing state returns the readiness error."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    mock_client.read_value = AsyncMock(return_value="initializing")
    mock_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "system_initializing"}

    mock_client.get_model_key.assert_not_awaited()
    mock_client.async_get_unique_id.assert_not_awaited()
    mock_client.close.assert_awaited()


async def test_validate_connection_desync(hass: HomeAssistant) -> None:
    """A deserialized desynchronized state returns the readiness error."""
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    mock_client.read_value = AsyncMock(return_value="desynchronized")
    mock_client.read_values.return_value = ReadResult.GATEWAY_NOT_READY

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], POWER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "desync_error"}

    mock_client.get_model_key.assert_not_awaited()
    mock_client.async_get_unique_id.assert_not_awaited()
    mock_client.close.assert_awaited()


async def test_validate_connection_invalid_slave(hass: HomeAssistant) -> None:
    """Test no model_key returns invalid_slave error."""
    mock_client = _mock_api_client()
    mock_client.get_model_key = AsyncMock(return_value=None)
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        _patch_cf_client(mock_gw_info),
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
        # unique_id now carries the per-unit H-LINK suffix (unit_id=0 default);
        # the flow derives the same value, so the duplicate is still caught (#370).
        unique_id=f"{DOMAIN}_ABCD1234_0",
    )
    existing_entry.add_to_hass(hass)

    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)
    mock_profs = _mock_profiles()

    result = await _advance_to_power(hass, mock_client, mock_gw_info, mock_profs)

    with (
        _patch_cf_client(mock_gw_info),
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
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
    assert result["step_id"] == "atw_mbs_02_connection"

    # Step 2: connection (provider step)
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": DEFAULT_NAME,
                CONF_MODBUS_HOST: "192.168.1.100",
                CONF_MODBUS_PORT: DEFAULT_PORT,
                CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
                "scan_interval": DEFAULT_SCAN_INTERVAL,
            },
        )
    assert result["step_id"] == "atw_mbs_02_variant"

    # Step 2b: variant (provider step)
    mock_profs = _mock_profiles()

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
        patch(_PATCH_ATW_PROFILES, mock_profs),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"gateway_variant": "gen1"},
        )
    assert result["step_id"] == "profile"

    # Step 3: profile
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile": "yutaki_s_combi"},
    )
    assert result["step_id"] == "sensors"

    # Step 4: sensors
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"power_supply": "three"},
    )
    # yutaki_s_combi exposes extended sensors: refrigerant consent step first.
    assert result["step_id"] == "advanced_features"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: True}},
    )
    assert result["step_id"] == "telemetry"

    # Step 5: telemetry
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"telemetry_level": "off"},
    )
    # Telemetry off: the fleet ping gets its own consent step.
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"fleet_ping": True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify data was updated
    assert entry.data[CONF_MODBUS_HOST] == "192.168.1.100"
    assert entry.data["profile"] == "yutaki_s_combi"
    assert entry.data["power_supply"] == "three"
    assert entry.data["gateway_variant"] == "gen1"


async def _walk_options_flow_to_sensors(
    hass: HomeAssistant, entry: MockConfigEntry, profile: str = "yutaki_s"
):
    """Drive the options flow from init up to (and including) the sensors form.

    Returns the flow result whose step_id is "sensors", ready for the caller to
    submit the sensors user_input.
    """
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"gateway_type": "modbus_atw_mbs_02"},
    )

    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": DEFAULT_NAME,
                CONF_MODBUS_HOST: DEFAULT_HOST,
                CONF_MODBUS_PORT: DEFAULT_PORT,
                CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
                "scan_interval": DEFAULT_SCAN_INTERVAL,
            },
        )

    mock_profs = _mock_profiles()
    with (
        patch(_PATCH_ATW_GW_INFO, mock_gw_info),
        patch(_PATCH_ATW_CREATE_RM),
        patch(_PATCH_ATW_PROFILES, mock_profs),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"gateway_variant": "gen1"},
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile": profile},
    )
    assert result["step_id"] == "sensors"
    return result


async def test_options_flow_clears_optional_sensor(hass: HomeAssistant) -> None:
    """Clearing a previously-configured optional sensor unsets it (#323)."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
            CONF_POWER_ENTITY: "sensor.old_power",
        },
    )
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_sensors(hass, entry)

    # Submit the sensors form with the power sensor cleared (omitted, as HA does).
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"power_supply": "single"},
    )
    assert result["step_id"] == "advanced_features"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: False}},
    )
    assert result["step_id"] == "telemetry"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"telemetry_level": "off"},
    )
    # Telemetry off: the fleet ping gets its own consent step.
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"fleet_ping": True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data.get(CONF_POWER_ENTITY) is None


async def test_options_flow_keeps_unset_optional_sensor_value(
    hass: HomeAssistant,
) -> None:
    """A sensor still present in the submitted input is preserved/updated."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
            CONF_ENERGY_ENTITY: "sensor.old_energy",
        },
    )
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_sensors(hass, entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "power_supply": "single",
            CONF_ENERGY_ENTITY: "sensor.new_energy",
        },
    )
    assert result["step_id"] == "advanced_features"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: False}},
    )
    assert result["step_id"] == "telemetry"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"telemetry_level": "off"},
    )
    # Telemetry off: the fleet ping gets its own consent step.
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"fleet_ping": True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_ENERGY_ENTITY] == "sensor.new_energy"


async def test_options_flow_preserves_unrelated_data_when_clearing_sensor(
    hass: HomeAssistant,
) -> None:
    """Reconciliation only touches the editable optional sensor keys (#323)."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
            CONF_POWER_ENTITY: "sensor.old_power",
        },
    )
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_sensors(hass, entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"power_supply": "single"},
    )
    assert result["step_id"] == "advanced_features"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: False}},
    )
    assert result["step_id"] == "telemetry"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"telemetry_level": "off"},
    )
    # Telemetry off: the fleet ping gets its own consent step.
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"fleet_ping": True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Cleared sensor is gone, but unrelated persisted data survives.
    assert entry.data.get(CONF_POWER_ENTITY) is None
    assert entry.data["gateway_variant"] == "gen1"
    assert entry.data["scan_interval"] == DEFAULT_SCAN_INTERVAL
    assert entry.data["profile"] == "yutaki_s"


async def test_options_flow_hides_refrigerant_toggle_for_yutampo(
    hass: HomeAssistant,
) -> None:
    """A Yutampo R32 entry still sees the panel, without the refrigerant toggle."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutampo_r32",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
    )
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_sensors(hass, entry, profile="yutampo_r32")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"power_supply": "single"},
    )
    # Unsupported profile: the panel is shown, but only with the cycling toggle.
    assert result["step_id"] == "advanced_features"
    section_schema = result["data_schema"].schema[SECTION_PREVENTIVE_MAINTENANCE]
    keys = {str(key) for key in section_schema.schema.schema}
    assert CONF_REFRIGERANT_DETECTION not in keys
    assert CONF_CYCLING_DETECTION in keys

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_CYCLING_DETECTION: False}},
    )
    assert result["step_id"] == "telemetry"


async def test_options_flow_persists_refrigerant_consent(
    hass: HomeAssistant,
) -> None:
    """Enabling consent lands in entry.options, never in entry.data."""
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
    )
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_sensors(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"power_supply": "single"},
    )
    assert result["step_id"] == "advanced_features"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: True}},
    )
    assert result["step_id"] == "telemetry"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"telemetry_level": "off"},
    )
    # Telemetry off: the fleet ping gets its own consent step.
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"fleet_ping": True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_REFRIGERANT_DETECTION] is True
    assert CONF_REFRIGERANT_DETECTION not in entry.data


def _fleet_ping_entry(options: dict | None = None) -> MockConfigEntry:
    """Entry ready for the options flow, with the given options."""
    return MockConfigEntry(
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
            "scan_interval": DEFAULT_SCAN_INTERVAL,
            "profile": "yutaki_s",
            "power_supply": DEFAULT_POWER_SUPPLY,
        },
        options=options or {},
    )


async def _walk_options_flow_to_telemetry(hass: HomeAssistant, entry: MockConfigEntry):
    """Drive the options flow up to the telemetry form."""
    result = await _walk_options_flow_to_sensors(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"power_supply": "single"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {SECTION_PREVENTIVE_MAINTENANCE: {CONF_REFRIGERANT_DETECTION: False}},
    )
    assert result["step_id"] == "telemetry"
    return result


async def test_options_flow_telemetry_on_skips_fleet_ping_step(
    hass: HomeAssistant,
) -> None:
    """Telemetry ON implies the fleet ping: its step is not shown (#468)."""
    entry = _fleet_ping_entry()
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_telemetry(hass, entry)
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"telemetry_level": "on"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["telemetry_level"] == "on"
    assert "fleet_ping" not in entry.options


async def test_options_flow_fleet_ping_opt_out(hass: HomeAssistant) -> None:
    """With telemetry off, turning the fleet ping off is persisted (#468)."""
    entry = _fleet_ping_entry({"fleet_ping": True})
    entry.add_to_hass(hass)

    result = await _walk_options_flow_to_telemetry(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"telemetry_level": "off"}
    )
    assert result["step_id"] == "fleet_ping"
    with patch.object(hass.config_entries, "async_reload"):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"fleet_ping": False}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["telemetry_level"] == "off"
    assert entry.options["fleet_ping"] is False


# ── Duplicate outdoor cycle (#404) ──


def _hc_a_entry(*, unit_id: int, outdoor_cycle: int, host: str = DEFAULT_HOST):
    return MockConfigEntry(
        version=2,
        minor_version=4,
        domain=DOMAIN,
        title=f"Unit {unit_id}",
        unique_id=f"{DOMAIN}_ABCD1234_{unit_id}",
        data={
            "gateway_type": "modbus_hc_a_mb",
            CONF_MODBUS_HOST: host,
            CONF_MODBUS_PORT: DEFAULT_PORT,
            CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
            "unit_id": unit_id,
            "outdoor_cycle": outdoor_cycle,
        },
    )


def _hc_a_config(*, unit_id: int, outdoor_cycle: int | None) -> dict:
    config = {
        "gateway_type": "modbus_hc_a_mb",
        "name": DEFAULT_NAME,
        CONF_MODBUS_HOST: DEFAULT_HOST,
        CONF_MODBUS_PORT: DEFAULT_PORT,
        CONF_MODBUS_DEVICE_ID: DEFAULT_DEVICE_ID,
        "unit_id": unit_id,
        "profile": "yutaki_s",
        "power_supply": DEFAULT_POWER_SUPPLY,
    }
    if outdoor_cycle is not None:
        config["outdoor_cycle"] = outdoor_cycle
    return config


def _flow(hass: HomeAssistant) -> HitachiYutakiConfigFlow:
    flow = HitachiYutakiConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {"source": config_entries.SOURCE_USER}
    return flow


async def test_validate_connection_refuses_duplicate_outdoor_cycle(
    hass: HomeAssistant,
) -> None:
    """Adding a unit on an outdoor cycle already in use shows an error (#404)."""
    _hc_a_entry(unit_id=0, outdoor_cycle=0).add_to_hass(hass)
    mock_client = _mock_api_client()
    mock_gw_info = _mock_gateway_info(mock_client)

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await _flow(hass).async_validate_connection(
            _hc_a_config(unit_id=3, outdoor_cycle=0)
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "outdoor_cycle_in_use"}


async def test_new_unit_on_a_moved_entrys_old_slot_is_not_refused(
    hass: HomeAssistant,
) -> None:
    """The unique_id uses (Ou, Iu), so a slot suffix left by a moved entry cannot collide (#476)."""
    moved = _hc_a_entry(unit_id=1, outdoor_cycle=5)  # unique_id ..._1, now elsewhere
    moved.add_to_hass(hass)
    config = {**_hc_a_config(unit_id=1, outdoor_cycle=7), "indoor_address": 8}
    flow = _flow(hass)
    mock_gw_info = _mock_gateway_info(_mock_api_client())

    with (
        _patch_cf_client(mock_gw_info),
    ):
        result = await flow.async_validate_connection(config)

    assert result.get("errors") in (None, {})
    assert flow.unique_id == f"{DOMAIN}_ABCD1234_c7_i8"


@pytest.mark.parametrize(
    ("variant", "raw_state", "error"),
    [
        ("gen2", 1, "desync_error"),
        ("gen2", 2, "system_initializing"),
        ("gen1", 2, "system_initializing"),
        ("hc_a_mb", 1, "desync_error"),
        ("hc_a_mb", 2, "system_initializing"),
        ("gen1", 1, None),
    ],
)
async def test_validation_uses_real_read_result_and_deserialized_state(
    hass: HomeAssistant, variant: str, raw_state: int, error: str | None
) -> None:
    """Real preflight decoding drives readiness, including nonblocking gen1 state 1."""

    maps = {
        "gen2": AtwMbs02RegisterMap,
        "gen1": AtwMbs02Pre2016RegisterMap,
        "hc_a_mb": HcAMbRegisterMap,
    }
    client = ModbusApiClient(hass, "test", "127.0.0.1", 502, 1, maps[variant]())
    client._client = MagicMock()
    client._client.is_socket_open.return_value = True
    response = MagicMock(registers=[raw_state])
    response.isError.return_value = False
    client._client.read_holding_registers.return_value = response
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.get_model_key = AsyncMock(return_value="yutaki_s")
    client.async_get_unique_id = AsyncMock(return_value="TEST")

    config = {
        **GATEWAY_CONFIG_INPUT,
        **PROFILE_INPUT,
        **POWER_INPUT,
        "gateway_type": "modbus_hc_a_mb"
        if variant == "hc_a_mb"
        else "modbus_atw_mbs_02",
    }
    with patch(
        "custom_components.hitachi_yutaki.config_flow.create_api_client",
        return_value=client,
    ):
        result = await _flow(hass).async_validate_connection(config)

    client.close.assert_awaited_once()
    if error:
        assert result["errors"] == {"base": error}
        client.get_model_key.assert_not_awaited()
        client.async_get_unique_id.assert_not_awaited()
        client._client.read_holding_registers.assert_called_once()
    else:
        assert result["step_id"] == "advanced_features"
        client.get_model_key.assert_awaited_once()


async def test_transport_error_is_normalized_by_provider(hass: HomeAssistant) -> None:
    """Transport failures reach the flow as cannot_connect and release the client."""
    client = _mock_api_client()
    client.read_values.side_effect = ModbusException("connection lost")
    config = {
        **GATEWAY_USER_INPUT,
        **GATEWAY_CONFIG_INPUT,
        **PROFILE_INPUT,
        **POWER_INPUT,
    }
    with patch(
        "custom_components.hitachi_yutaki.config_flow.create_api_client",
        return_value=client,
    ):
        result = await _flow(hass).async_validate_connection(config)
    assert result["errors"] == {"base": "cannot_connect"}
    client.get_model_key.assert_not_awaited()
    client.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("gateway_type", "unit_data", "suffix"),
    [
        ("modbus_atw_mbs_02", {}, "0"),
        ("modbus_hc_a_mb", {"unit_id": 3}, "3"),
        (
            "modbus_hc_a_mb",
            {"unit_id": 3, "outdoor_cycle": 5, "indoor_address": 6},
            "c5_i6",
        ),
    ],
)
async def test_flow_preserves_provider_fallback_identity(
    hass: HomeAssistant, gateway_type: str, unit_data: dict, suffix: str
) -> None:
    """Failed hardware identification preserves each gateway's exact fallback ID."""
    client = _mock_api_client()
    client.async_get_unique_id.return_value = None
    config = {
        **GATEWAY_CONFIG_INPUT,
        **PROFILE_INPUT,
        **POWER_INPUT,
        "gateway_type": gateway_type,
        **unit_data,
    }
    flow = _flow(hass)
    with patch(
        "custom_components.hitachi_yutaki.config_flow.create_api_client",
        return_value=client,
    ):
        result = await flow.async_validate_connection(config)
    assert result["step_id"] == "advanced_features"
    assert flow.unique_id == f"{DEFAULT_HOST}_{DEFAULT_DEVICE_ID}_{suffix}"
