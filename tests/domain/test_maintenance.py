"""Pure maintenance warning policies and their persistence boundaries."""

from dataclasses import replace

import pytest

from custom_components.hitachi_yutaki.domain.models.cycling import CyclingStatus
from custom_components.hitachi_yutaki.domain.models.maintenance import MaintenanceAlert
from custom_components.hitachi_yutaki.domain.models.refrigerant import RefrigerantStatus
from custom_components.hitachi_yutaki.domain.services.maintenance import (
    cycling_alert_policy,
    refrigerant_alert_policy,
)
from custom_components.hitachi_yutaki.domain.services.refrigerant import (
    ALERT_PERSIST_DAYS,
    STALE_AFTER_DAYS,
)

_REFRIGERANT = RefrigerantStatus(
    status="alert",
    superheat_delta=6.0,
    exv_delta=20.0,
    evaporation_temp_delta=-3.0,
    baseline=None,
    valid_days=21,
    today_samples=0,
    alert_streak=ALERT_PERSIST_DAYS,
)
_CYCLING = CyclingStatus(
    status="alert",
    cycles_today=0,
    peak_starts_today=None,
    median_period_today=None,
    median_run_today=None,
    valid_days=3,
    alert_streak=3,
)


@pytest.mark.parametrize("policy", [refrigerant_alert_policy, cycling_alert_policy])
def test_no_detector_means_no_warning(policy):
    """No detector status cannot produce a maintenance warning."""
    assert policy(None) == MaintenanceAlert()


@pytest.mark.parametrize("streak", [0, ALERT_PERSIST_DAYS - 1])
def test_refrigerant_alert_status_is_not_a_persistent_warning(streak):
    """The sensor can show alert before the warning persistence threshold."""
    status = replace(_REFRIGERANT, alert_streak=streak, days_since_valid_data=100)
    assert refrigerant_alert_policy(status) == MaintenanceAlert()


@pytest.mark.parametrize(
    ("age", "stale"),
    [
        (None, False),
        (STALE_AFTER_DAYS, False),
        (STALE_AFTER_DAYS + 1, True),
        (365, True),
    ],
)
def test_refrigerant_staleness_does_not_clear_sustained_warning(age, stale):
    """A frozen off-season warning remains active and gains stale metadata."""
    assert refrigerant_alert_policy(
        replace(_REFRIGERANT, days_since_valid_data=age)
    ) == MaintenanceAlert(True, stale)


def test_refrigerant_recovery_clears_warning():
    """A recovered detector resets its streak and clears the warning."""
    assert (
        refrigerant_alert_policy(replace(_REFRIGERANT, status="ok", alert_streak=0))
        == MaintenanceAlert()
    )


@pytest.mark.parametrize("verdict", ["learning", "ok", "watch"])
def test_cycling_policy_uses_monitor_verdict(verdict):
    """A non-alert verdict cannot be overridden by an independently read streak."""
    assert cycling_alert_policy(replace(_CYCLING, status=verdict)) == MaintenanceAlert()


def test_cycling_expiry_is_owned_by_the_monitor():
    """The warning policy must not add another age-based expiry rule."""
    assert cycling_alert_policy(
        replace(_CYCLING, days_since_valid_day=365)
    ) == MaintenanceAlert(True, False)
