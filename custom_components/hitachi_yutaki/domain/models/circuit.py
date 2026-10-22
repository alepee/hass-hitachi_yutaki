"""Normalized circuit activity inputs and verdicts."""

from dataclasses import dataclass
from enum import StrEnum


class CircuitActivity(StrEnum):
    """Activity of a space-conditioning circuit, independent of HA."""

    OFF = "off"
    IDLE = "idle"
    HEATING = "heating"
    COOLING = "cooling"
    DEFROSTING = "defrosting"


@dataclass(frozen=True)
class CircuitActivityInput:
    """Circuit power and unit activity normalized by the adapter.

    Unit mode is a fallback only when the operation state is unavailable.
    An available state with no active operation mode denotes inactivity.
    """

    powered: bool | None
    compressor_running: bool
    defrosting: bool
    operation_mode: str | None
    operation_state_available: bool
    unit_mode: str | None
