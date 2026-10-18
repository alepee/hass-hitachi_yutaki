"""Pure circuit activity regressions."""

from dataclasses import replace

import pytest

from custom_components.hitachi_yutaki.domain.models.circuit import (
    CircuitActivity,
    CircuitActivityInput,
)
from custom_components.hitachi_yutaki.domain.models.operation import (
    MODE_COOLING,
    MODE_DHW,
    MODE_HEATING,
    MODE_POOL,
)
from custom_components.hitachi_yutaki.domain.services.circuit import (
    resolve_circuit_activity,
)

_RUNNING = CircuitActivityInput(
    powered=True,
    compressor_running=True,
    defrosting=False,
    operation_mode=MODE_HEATING,
    operation_state_available=True,
    unit_mode=MODE_HEATING,
)


@pytest.mark.parametrize("unit_mode", [MODE_HEATING, MODE_COOLING, None])
@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (MODE_HEATING, CircuitActivity.HEATING),
        (MODE_COOLING, CircuitActivity.COOLING),
        (MODE_DHW, CircuitActivity.IDLE),
        (MODE_POOL, CircuitActivity.IDLE),
        (None, CircuitActivity.IDLE),
    ],
)
def test_actual_operation_takes_precedence(unit_mode, operation, expected):
    """Compressor work on another load never means space heating/cooling."""
    data = replace(_RUNNING, operation_mode=operation, unit_mode=unit_mode)
    assert resolve_circuit_activity(data) == expected


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"powered": False, "defrosting": True}, CircuitActivity.OFF),
        ({"powered": None}, None),
        ({"defrosting": True, "compressor_running": False}, CircuitActivity.DEFROSTING),
        ({"compressor_running": False}, CircuitActivity.IDLE),
    ],
)
def test_power_defrost_and_compressor_precedence(changes, expected):
    """Keep circuit power and defrost precedence when resolving activity."""
    assert resolve_circuit_activity(replace(_RUNNING, **changes)) == expected


@pytest.mark.parametrize(
    ("unit_mode", "expected"),
    [
        (MODE_HEATING, CircuitActivity.HEATING),
        (MODE_COOLING, CircuitActivity.COOLING),
        (None, None),
    ],
)
def test_missing_operation_state_keeps_fixed_mode_fallback(unit_mode, expected):
    """Gateways without activity data retain explicit heat/cool behavior."""
    data = replace(
        _RUNNING,
        operation_mode=None,
        operation_state_available=False,
        unit_mode=unit_mode,
    )
    assert resolve_circuit_activity(data) == expected
