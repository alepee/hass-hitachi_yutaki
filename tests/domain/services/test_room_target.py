"""Tests for the room target keeper (#511)."""

from custom_components.hitachi_yutaki.domain.services.room_target import (
    CONFIRM_AFTER_S,
    MAX_RESTORE_ATTEMPTS,
    RoomRestore,
    RoomTargetKeeper,
    is_valid_target,
)


def test_valid_range_is_the_documented_register_range():
    """5.0-35.0 °C is a target; 0 and an unread value are not."""
    assert is_valid_target(5.0)
    assert is_valid_target(35.0)
    assert not is_valid_target(0.0)
    assert not is_valid_target(4.9)
    assert not is_valid_target(None)


def test_a_valid_reading_is_remembered_and_marks_dirty_once():
    """Each new valid target is stored; an unchanged one is not re-saved."""
    keeper = RoomTargetKeeper()
    assert keeper.observe(1, True, 22.0, now=0) == RoomRestore()
    assert keeper.stored_target(1) == 22.0
    assert keeper.take_dirty() is True
    assert keeper.take_dirty() is False
    keeper.observe(1, True, 22.0, now=5)
    assert keeper.take_dirty() is False


def test_zero_with_the_sensor_on_restores_the_last_valid_target():
    """The #511 board reset: target 0, flag still on, stored target written back."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    assert keeper.observe(1, True, 0.0, now=10).target == 22.0


def test_nothing_to_restore_with_the_sensor_off():
    """With the flag off the unit ignores the room registers: no write."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, False, 22.0, now=0)
    assert keeper.observe(1, False, 0.0, now=10) == RoomRestore()


def test_nothing_to_restore_without_a_remembered_target():
    """No valid target ever seen: nothing sensible to write."""
    keeper = RoomTargetKeeper()
    assert keeper.observe(1, True, 0.0, now=0) == RoomRestore()


def test_unread_values_decide_nothing():
    """A failed read neither stores nor restores."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    assert keeper.observe(1, None, 0.0, now=10) == RoomRestore()
    assert keeper.observe(1, True, None, now=10) == RoomRestore()
    assert keeper.failed_circuits() == []


def test_a_user_change_becomes_the_target_to_restore():
    """A deliberate new setpoint is just a newer valid target."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    keeper.observe(1, True, 19.5, now=100)
    assert keeper.observe(1, True, 0.0, now=200).target == 19.5


def test_the_echo_of_its_own_write_does_not_confirm_a_restore():
    """The client shows the written value for 30 s: only a later read counts."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    for attempt in range(MAX_RESTORE_ATTEMPTS):
        start = 100 + attempt * 35
        assert keeper.observe(1, True, 0.0, now=start).target == 22.0
        keeper.observe(1, True, 22.0, now=start + 5)  # shadowed echo
    assert keeper.observe(1, True, 0.0, now=300).target is None
    assert keeper.failed_circuits() == [1]


def test_a_confirmed_restore_resets_the_attempts():
    """A valid read after the shadow expired confirms the restore."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    assert keeper.observe(1, True, 0.0, now=100).target == 22.0
    keeper.observe(1, True, 22.0, now=100 + CONFIRM_AFTER_S)
    for attempt in range(MAX_RESTORE_ATTEMPTS):
        assert keeper.observe(1, True, 0.0, now=1000 + attempt).target == 22.0
    assert keeper.failed_circuits() == []


def test_failure_clears_once_a_valid_target_is_read():
    """Setting the target by hand ends the failed state."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    for attempt in range(MAX_RESTORE_ATTEMPTS + 1):
        keeper.observe(1, True, 0.0, now=100 + attempt)
    assert keeper.failed_circuits() == [1]
    keeper.observe(1, True, 21.0, now=1000)
    assert keeper.failed_circuits() == []


def test_circuits_are_independent():
    """Circuit 2 keeps its own target."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    keeper.observe(2, True, 18.0, now=0)
    assert keeper.observe(2, True, 0.0, now=10).target == 18.0
    assert keeper.observe(1, True, 22.0, now=10).target is None


def test_serialize_round_trip_survives_a_restart():
    """Remembered values are restored from the snapshot; junk is dropped."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0, keep_enabled=True)
    keeper.observe(2, True, 18.5, now=0)
    restored = RoomTargetKeeper(keeper.serialize())
    assert restored.stored_target(1) == 22.0
    assert restored.stored_target(2) == 18.5
    assert restored.stored_enabled(1) is True
    assert restored.stored_enabled(2) is False
    assert restored.observe(1, True, 0.0, now=0).target == 22.0

    junk = RoomTargetKeeper({"targets": {"1": "x", "2": 0, "x": 20}, "enabled": 3})
    assert junk.stored_target(1) is None
    assert junk.stored_target(2) is None
    assert RoomTargetKeeper(None).serialize() == {"targets": {}, "enabled": {}}


# --- External room sensor flag (gateway reset) ---


def _kept(keeper: RoomTargetKeeper, enabled, target, now, *, after_gap=False):
    return keeper.observe(
        1, enabled, target, now, keep_enabled=True, after_gap=after_gap
    )


def test_a_flag_lowered_across_a_gap_is_raised_again():
    """The gateway reset: flag off on the first good poll after a failure."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    decision = _kept(keeper, False, 22.0, now=100, after_gap=True)
    assert decision == RoomRestore(target=None, enable=True)


def test_a_flag_lowered_while_connected_was_lowered_by_the_user():
    """No gap: Home Assistant turned the switch off, so it stays off."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    assert _kept(keeper, False, 22.0, now=100).enable is False
    assert keeper.stored_enabled(1) is False
    assert _kept(keeper, False, 22.0, now=200, after_gap=True).enable is False


def test_the_flag_is_only_kept_when_asked():
    """Without the opt-in the flag is neither remembered nor raised."""
    keeper = RoomTargetKeeper()
    keeper.observe(1, True, 22.0, now=0)
    assert keeper.stored_enabled(1) is False
    assert keeper.observe(1, False, 22.0, now=100, after_gap=True).enable is False


def test_a_flag_never_seen_on_is_left_alone():
    """A water-law installation never had the flag up: nothing to raise."""
    keeper = RoomTargetKeeper()
    assert _kept(keeper, False, 22.0, now=0, after_gap=True).enable is False


def test_both_lost_restores_the_target_first_and_raises_the_flag():
    """A full power cut: the target is written in the same decision as the flag."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    decision = _kept(keeper, False, 0.0, now=100, after_gap=True)
    assert decision == RoomRestore(target=22.0, enable=True)


def test_the_flag_is_not_raised_on_a_target_of_zero():
    """No valid target to regulate on: wait for one before raising the flag."""
    keeper = RoomTargetKeeper({"enabled": {"1": True}})
    assert _kept(keeper, False, 0.0, now=100, after_gap=True) == RoomRestore()
    # The wish survives the gap; the flag goes up once the target is back.
    assert _kept(keeper, False, 0.0, now=200) == RoomRestore()
    assert _kept(keeper, False, 21.0, now=300).enable is True


def test_the_echo_of_the_flag_write_does_not_confirm_it():
    """Three unconfirmed raises: give up and report the circuit."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    assert _kept(keeper, False, 22.0, now=100, after_gap=True).enable is True
    for attempt in range(1, MAX_RESTORE_ATTEMPTS):
        _kept(keeper, True, 22.0, now=100 + attempt * 35 - 30)  # shadowed echo
        assert _kept(keeper, False, 22.0, now=100 + attempt * 35).enable is True
    assert _kept(keeper, False, 22.0, now=300).enable is False
    assert keeper.failed_flag_circuits() == [1]
    assert keeper.stored_enabled(1) is True


def test_a_confirmed_flag_ends_the_restore():
    """Read on past the shadow: the attempts reset and failure clears."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    for attempt in range(MAX_RESTORE_ATTEMPTS + 1):
        _kept(keeper, False, 22.0, now=100 + attempt, after_gap=True)
    assert keeper.failed_flag_circuits() == [1]
    _kept(keeper, True, 22.0, now=1000)
    assert keeper.failed_flag_circuits() == []
    assert _kept(keeper, False, 22.0, now=2000, after_gap=True).enable is True


def test_turning_the_option_off_drops_a_failed_flag():
    """Without the opt-in there is nothing left to report."""
    keeper = RoomTargetKeeper()
    _kept(keeper, True, 22.0, now=0)
    for attempt in range(MAX_RESTORE_ATTEMPTS + 1):
        _kept(keeper, False, 22.0, now=100 + attempt, after_gap=True)
    assert keeper.failed_flag_circuits() == [1]
    keeper.observe(1, False, 22.0, now=500)
    assert keeper.failed_flag_circuits() == []
