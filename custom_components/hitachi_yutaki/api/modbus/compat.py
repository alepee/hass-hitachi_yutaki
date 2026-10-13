"""Compatibility with supported pymodbus versions."""

from packaging import version
import pymodbus


def get_pymodbus_device_param() -> str:
    """Get the correct parameter name for pymodbus device/slave based on version.

    Returns:
        str: 'device_id' for pymodbus >= 3.10.0, 'slave' for older versions

    """
    try:
        pymodbus_version = version.parse(pymodbus.__version__)
        if pymodbus_version >= version.parse("3.10.0"):
            return "device_id"
        else:
            return "slave"
    except (ImportError, AttributeError):
        # Fallback to 'slave' if pymodbus is not available or version cannot be determined
        return "slave"
