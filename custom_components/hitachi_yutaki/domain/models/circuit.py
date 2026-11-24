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
    UNKNOWN = "unknown"
    """The observations do not establish what the circuit is doing."""


@dataclass(frozen=True)
class CircuitActivityInput:
    """Circuit power and unit activity normalized by the adapter.

    The operation state is the only evidence of what a running compressor
    serves. When it is unavailable, the selected global mode is no substitute:
    the unit may be producing DHW or heating the pool. An available state with
    no active operation mode denotes inactivity.
    """

    powered: bool | None
    compressor_running: bool
    defrosting: bool
    operation_mode: str | None
    operation_state_available: bool
