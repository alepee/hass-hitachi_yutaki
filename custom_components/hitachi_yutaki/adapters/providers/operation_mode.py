"""Operation mode provider — bridges Modbus state to domain mode."""

from ...domain.models.operation import (
    MODE_COOLING,
    MODE_DHW,
    MODE_HEATING,
    MODE_POOL,
)

# Maps deserialized Modbus operation_state to domain operation mode.
# Only active states are mapped — transitional states (demand_off, thermo_off) return None.
# The cycling detector needs a wider view, see resolve_cycling_regime below.
_OPERATION_STATE_TO_MODE: dict[str, str] = {
    "operation_state_heat_thermo_on": MODE_HEATING,
    "operation_state_cool_thermo_on": MODE_COOLING,
    "operation_state_dhw_on": MODE_DHW,
    "operation_state_pool_on": MODE_POOL,
}


def resolve_operation_mode(operation_state: str | None) -> str | None:
    """Resolve a Modbus operation state string to a domain operation mode."""
    if operation_state is None:
        return None
    return _OPERATION_STATE_TO_MODE.get(operation_state)


def get_accepted_operation_states(mode: str) -> set[str]:
    """Return Modbus operation state keys that match a given domain mode."""
    return {raw for raw, m in _OPERATION_STATE_TO_MODE.items() if m == mode}


# Regime a compressor cycle belongs to. In space heating, thermo-off is the
# controller stopping the compressor once the water target is reached, and
# demand-off a room thermostat ending the demand: both are the off half of a
# heating cycle, not a different regime. Resolving them to None broke the cycle
# chain at every stop, so no period was ever measured. Only space heating is
# evaluated by the detector, so cooling transitional states are left unmapped.
_OPERATION_STATE_TO_CYCLING_REGIME: dict[str, str] = {
    **_OPERATION_STATE_TO_MODE,
    "operation_state_heat_thermo_off": MODE_HEATING,
    "operation_state_heat_demand_off": MODE_HEATING,
}


def resolve_cycling_regime(operation_state: str | None) -> str | None:
    """Resolve a Modbus operation state to the regime a compressor cycle belongs to."""
    if operation_state is None:
        return None
    return _OPERATION_STATE_TO_CYCLING_REGIME.get(operation_state)
