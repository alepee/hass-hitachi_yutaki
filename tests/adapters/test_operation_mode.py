"""Unit tests for the operation-state to regime resolvers."""

from __future__ import annotations

import pytest

from custom_components.hitachi_yutaki.adapters.providers.operation_mode import (
    resolve_cycling_regime,
    resolve_operation_mode,
)
from custom_components.hitachi_yutaki.domain.models.operation import MODE_HEATING


@pytest.mark.parametrize(
    "state",
    [
        "operation_state_heat_thermo_on",
        "operation_state_heat_thermo_off",
        "operation_state_heat_demand_off",
    ],
)
def test_heating_off_phases_stay_in_the_heating_regime(state: str) -> None:
    """Thermo-off and demand-off are the off half of a heating cycle."""
    assert resolve_cycling_regime(state) == MODE_HEATING


@pytest.mark.parametrize(
    "state",
    [
        "operation_state_off",
        "operation_state_dhw_on",
        "operation_state_dhw_off",
        "operation_state_pool_on",
        "operation_state_pool_off",
        "operation_state_cool_thermo_on",
        "operation_state_cool_thermo_off",
        "operation_state_alarm",
        "operation_state_unknown",
        None,
    ],
)
def test_other_states_are_not_heating(state: str | None) -> None:
    """Any other regime, or no regime at all, must break the heating chain."""
    assert resolve_cycling_regime(state) != MODE_HEATING


def test_operation_mode_keeps_transitional_states_unmapped() -> None:
    """The general resolver is unchanged: only active states map to a mode."""
    assert resolve_operation_mode("operation_state_heat_thermo_off") is None
    assert resolve_operation_mode("operation_state_heat_demand_off") is None
