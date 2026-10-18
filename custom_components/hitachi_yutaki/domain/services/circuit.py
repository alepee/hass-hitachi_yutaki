"""Resolve space-conditioning activity without confusing DHW with heating."""

from ..models.circuit import CircuitActivity, CircuitActivityInput
from ..models.operation import MODE_COOLING, MODE_HEATING


def resolve_circuit_activity(data: CircuitActivityInput) -> CircuitActivity | None:
    """Return the circuit verdict, preferring actual activity over unit mode."""
    if data.powered is None:
        return None
    if not data.powered:
        return CircuitActivity.OFF
    if data.defrosting:
        return CircuitActivity.DEFROSTING
    if not data.compressor_running:
        return CircuitActivity.IDLE
    if data.operation_state_available:
        if data.operation_mode == MODE_HEATING:
            return CircuitActivity.HEATING
        if data.operation_mode == MODE_COOLING:
            return CircuitActivity.COOLING
        return CircuitActivity.IDLE
    if data.unit_mode == MODE_HEATING:
        return CircuitActivity.HEATING
    if data.unit_mode == MODE_COOLING:
        return CircuitActivity.COOLING
    return None
