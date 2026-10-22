"""Regression tests for the domain-owned energy and cost accumulation policy."""

import pytest

from custom_components.hitachi_yutaki.domain.services.electrical_energy import (
    ElectricalEnergyAccumulator,
)


@pytest.mark.parametrize(
    ("interval", "elapsed", "expected_seconds"),
    [(5, 25, 25), (5, 3600, 30), (60, 3600, 180), (5, -10, 0)],
)
def test_gap_tolerance_and_nonnegative_energy(
    clock, interval, elapsed, expected_seconds
):
    """Integrate ordinary polls, bound outages and ignore backward time."""
    accumulator = ElectricalEnergyAccumulator(interval, clock=clock)
    accumulator.update(3.6, 0.25)
    clock.seconds += elapsed
    accumulator.update(3.6, 0.25)
    assert accumulator.energy == pytest.approx(expected_seconds / 1000)
    assert accumulator.cost == pytest.approx(expected_seconds / 1000 * 0.25)


def test_tariffs_missing_price_negative_price_and_restoration(clock):
    """Restoration adds no downtime; only newly priced energy changes cost."""
    accumulator = ElectricalEnergyAccumulator(5, clock=clock)
    accumulator.restore_energy(10)
    accumulator.restore_cost(3)
    accumulator.update(3.6, 0.2)
    assert (accumulator.energy, accumulator.cost) == (10, 3)
    for price in (0.2, None, -0.1):
        clock.seconds += 10
        accumulator.update(3.6, price)
    assert accumulator.energy == pytest.approx(10.03)
    assert accumulator.cost == pytest.approx(3.001)
