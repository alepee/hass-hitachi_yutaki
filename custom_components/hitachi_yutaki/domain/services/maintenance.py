"""Pure warning policies for preventive maintenance detectors."""

from ..models.cycling import CyclingStatus
from ..models.maintenance import MaintenanceAlert
from ..models.refrigerant import RefrigerantStatus
from .cycling import STATUS_ALERT as CYCLING_STATUS_ALERT
from .refrigerant import ALERT_PERSIST_DAYS, STALE_AFTER_DAYS


def refrigerant_alert_policy(status: RefrigerantStatus | None) -> MaintenanceAlert:
    """Require a sustained refrigerant streak and annotate frozen evidence.

    A refrigerant alert status alone is not a persistent warning. Off-season
    evidence gets stale but must not silently clear a sustained warning.
    """
    if status is None or status.alert_streak < ALERT_PERSIST_DAYS:
        return MaintenanceAlert()
    return MaintenanceAlert(
        persistent=True,
        stale=(
            status.days_since_valid_data is not None
            and status.days_since_valid_data > STALE_AFTER_DAYS
        ),
    )


def cycling_alert_policy(status: CyclingStatus | None) -> MaintenanceAlert:
    """Use the monitor's persistent verdict; expiry belongs to that monitor."""
    return MaintenanceAlert(
        persistent=status is not None and status.status == CYCLING_STATUS_ALERT
    )
