"""Domain test dependencies."""

import pytest

from .clock import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    """Return an independently controllable clock for each test."""
    return FakeClock()
