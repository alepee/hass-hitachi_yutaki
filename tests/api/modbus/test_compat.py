"""Pymodbus parameter compatibility remains inside the API implementation."""

from unittest.mock import patch

import pytest

from custom_components.hitachi_yutaki.api.modbus.compat import get_pymodbus_device_param


@pytest.mark.parametrize(
    ("version", "parameter"),
    [("3.9.2", "slave"), ("3.10.0", "device_id"), ("3.11.3", "device_id")],
)
def test_device_parameter(version: str, parameter: str) -> None:
    """The version boundary preserves the correct device addressing keyword."""
    with patch(
        "custom_components.hitachi_yutaki.api.modbus.compat.pymodbus.__version__",
        version,
    ):
        assert get_pymodbus_device_param() == parameter
