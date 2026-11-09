"""Test the gateway outage timer and warning throttle (#356)."""

from __future__ import annotations

from custom_components.hitachi_yutaki.api.modbus.outage import (
    REMINDER_INTERVAL,
    GatewayOutage,
    NotReadyWarning,
)


def test_first_not_ready_poll_warns_and_starts_the_timer():
    """The first not-ready poll warns and records when the outage began."""
    outage = GatewayOutage()

    assert outage.not_ready(1000.0) is NotReadyWarning.FIRST
    assert outage.since == 1000.0


def test_reminder_is_throttled_to_the_interval():
    """Later polls stay silent until a reminder is due, then the clock rearms."""
    outage = GatewayOutage()
    outage.not_ready(1000.0)

    assert outage.not_ready(1000.0 + REMINDER_INTERVAL - 1) is None
    assert outage.not_ready(1000.0 + REMINDER_INTERVAL) is NotReadyWarning.REMINDER
    assert outage.not_ready(1000.0 + REMINDER_INTERVAL + 1) is None
    assert outage.not_ready(1000.0 + 2 * REMINDER_INTERVAL) is NotReadyWarning.REMINDER
    assert outage.duration(1000.0 + 2 * REMINDER_INTERVAL) == 2 * REMINDER_INTERVAL


def test_ready_after_an_outage_reports_its_duration_and_resets():
    """Recovery returns how long the outage lasted and clears the state."""
    outage = GatewayOutage()
    outage.not_ready(1000.0)
    outage.not_ready(1100.0)

    assert outage.ready(1125.0) == 125.0
    assert outage.since is None
    assert outage.last_warning == 0.0
    assert outage.not_ready(2000.0) is NotReadyWarning.FIRST


def test_ready_without_an_outage_reports_nothing():
    """A ready poll with no outage in progress is not a recovery."""
    outage = GatewayOutage()

    assert outage.ready(1000.0) is None
    assert outage.duration(1000.0) == 0.0


def test_backward_clock_never_yields_a_negative_duration():
    """A time earlier than the outage start counts as zero, not negative."""
    outage = GatewayOutage()
    outage.not_ready(1000.0)

    assert outage.duration(900.0) == 0.0
    assert outage.ready(900.0) == 0.0


def test_custom_reminder_interval():
    """The reminder interval is configurable."""
    outage = GatewayOutage(reminder_interval=10.0)
    outage.not_ready(0.0)

    assert outage.not_ready(10.0) is NotReadyWarning.REMINDER
