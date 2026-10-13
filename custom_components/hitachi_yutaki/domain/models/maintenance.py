"""Presentation-independent preventive maintenance decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MaintenanceAlert:
    """Whether a persistent warning is warranted and its evidence is stale.

    Persistence describes the detector warning, not HA issue storage.
    """

    persistent: bool = False
    stale: bool = False
