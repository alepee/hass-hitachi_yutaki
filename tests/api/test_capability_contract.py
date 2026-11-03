"""Public key and mode capabilities of concrete gateway clients."""

from unittest.mock import MagicMock

import pytest

from custom_components.hitachi_yutaki.api.base import HitachiApiClient
from custom_components.hitachi_yutaki.api.modbus import ModbusApiClient
from custom_components.hitachi_yutaki.api.modbus.registers import RegisterDefinition
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02 import (
    AtwMbs02RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.atw_mbs_02_pre2016 import (
    AtwMbs02Pre2016RegisterMap,
)
from custom_components.hitachi_yutaki.api.modbus.registers.hc_a_mb import (
    HcAMbRegisterMap,
)


@pytest.mark.parametrize(
    ("map_class", "modes"),
    [
        (AtwMbs02RegisterMap, ("cool", "heat", "auto")),
        (AtwMbs02Pre2016RegisterMap, ("cool", "heat")),
        (HcAMbRegisterMap, ("cool", "heat")),
    ],
)
def test_public_capabilities_match_writable_keys(map_class, modes) -> None:
    """Callers need neither register addresses nor the map for optional controls."""
    client = ModbusApiClient(MagicMock(), "test", "127.0.0.1", 502, 1, map_class())
    assert client.supported_unit_modes == modes
    assert client.supports_key("system_state")
    assert not client.can_write("system_state")
    assert client.can_write("unit_mode")
    assert not client.supports_key("nonexistent")
    assert not client.can_write("nonexistent")
    assert "system_state" in client.gateway_keys
    assert "unit_mode" in client.base_keys
    assert not hasattr(HitachiApiClient, "register_map")
    # Consumers cannot corrupt the map's lists by changing their requested keys.
    client.base_keys.clear()
    client.gateway_keys.clear()
    assert client.base_keys
    assert client.gateway_keys


def test_nonwritable_mode_has_no_supported_options() -> None:
    """A read-only global mode must not advertise writeable selections."""
    rmap = MagicMock(
        all_registers={"unit_mode": RegisterDefinition(1051)},
        writable_keys=set(),
        hvac_unit_mode_cool=0,
        hvac_unit_mode_heat=1,
        hvac_unit_mode_auto=2,
    )
    client = ModbusApiClient(MagicMock(), "test", "127.0.0.1", 502, 1, rmap)
    assert client.supports_key("unit_mode")
    assert not client.can_write("unit_mode")
    assert client.supported_unit_modes == ()
