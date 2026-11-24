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
)


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
def test_actual_operation_takes_precedence(operation, expected):
    """Compressor work on another load never means space heating/cooling."""
    data = replace(_RUNNING, operation_mode=operation)
    assert resolve_circuit_activity(data) == expected


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"powered": False, "defrosting": True}, CircuitActivity.OFF),
        ({"powered": None}, CircuitActivity.UNKNOWN),
        ({"defrosting": True, "compressor_running": False}, CircuitActivity.DEFROSTING),
        ({"compressor_running": False}, CircuitActivity.IDLE),
    ],
)
def test_power_defrost_and_compressor_precedence(changes, expected):
    """Keep circuit power and defrost precedence when resolving activity."""
    assert resolve_circuit_activity(replace(_RUNNING, **changes)) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"operation_mode": MODE_DHW},
        {"operation_mode": MODE_POOL},
        {"operation_mode": MODE_COOLING},
    ],
)
def test_unreadable_operation_state_is_unknown(changes):
    """Without the operation state, a running compressor proves no circuit load.

    The unit may be producing DHW or heating the pool: the selected global mode
    cannot tell, so the verdict is UNKNOWN rather than a guessed HEATING.
    """
    data = replace(_RUNNING, **changes, operation_state_available=False)
    assert resolve_circuit_activity(data) == CircuitActivity.UNKNOWN


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"powered": False}, CircuitActivity.OFF),
        ({"defrosting": True}, CircuitActivity.DEFROSTING),
        ({"compressor_running": False}, CircuitActivity.IDLE),
    ],
)
def test_unreadable_operation_state_keeps_known_verdicts(changes, expected):
    """Power, defrost and a stopped compressor stay conclusive on their own."""
    data = replace(_RUNNING, **changes, operation_state_available=False)
    assert resolve_circuit_activity(data) == expected
