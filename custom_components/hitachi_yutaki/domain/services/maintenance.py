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


# Variants of the short-cycling repair text (#512).
CYCLING_ADVICE_GENERIC = "generic"
CYCLING_ADVICE_DIAGNOSED = "diagnosed"
CYCLING_ADVICE_CASCADE = "diagnosed_cascade"

# Share of settled run time with the secondary compressor on, above which the
# cascade hint applies: occasional engagement is not what drives the cycling.
CASCADE_SHARE_THRESHOLD = 0.2


def _fmt(value: float | None, digits: int = 1) -> str:
    """Format a number for a repair placeholder."""
    if value is None:
        return "?"
    return f"{value:.{digits}f}" if digits else str(round(value))


def cycling_advice(status: CyclingStatus | None) -> tuple[str, dict[str, str]]:
    """Choose the short-cycling repair text and fill it with the unit's numbers.

    Without a measured heat balance (no flow reading, or no cycle closed by a
    thermo-off yet), the generic causes are listed. With one, the text gives
    the installation's own output, absorbed heat and loop volume. On a cascade
    unit whose secondary compressor runs a significant share of the time, it
    adds the water target at which that compressor engages.
    """
    diagnosis = status.diagnosis if status is not None else None
    if diagnosis is None:
        return CYCLING_ADVICE_GENERIC, {}

    placeholders = {
        "days": str(status.diagnosis_days if status is not None else 0),
        "output_kw": _fmt(diagnosis.output_kw),
        "absorbed_kw": _fmt(diagnosis.absorbed_kw),
        "load_pct": _fmt(diagnosis.load_ratio * 100, 0),
        "volume_l": _fmt(diagnosis.loop_volume_l, 0),
        "run_min": _fmt(diagnosis.run_min),
        "rest_min": _fmt(diagnosis.rest_min),
        "floor_pct": _fmt(
            diagnosis.floor_share * 100 if diagnosis.floor_share is not None else None,
            0,
        ),
    }
    if (
        diagnosis.secondary_share is not None
        and diagnosis.secondary_share >= CASCADE_SHARE_THRESHOLD
        and diagnosis.secondary_target_c is not None
    ):
        placeholders["secondary_pct"] = _fmt(diagnosis.secondary_share * 100, 0)
        placeholders["secondary_target"] = _fmt(diagnosis.secondary_target_c, 0)
        return CYCLING_ADVICE_CASCADE, placeholders
    return CYCLING_ADVICE_DIAGNOSED, placeholders
