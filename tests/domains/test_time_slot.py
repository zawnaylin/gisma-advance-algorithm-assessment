from calendar import MONDAY, SATURDAY, TUESDAY

import pytest

from data.constraints import END_TIME, START_TIME
from domains.time_slot import TimeSlot


def test_valid_slot_holds_its_values():
    slot = TimeSlot(MONDAY, START_TIME, START_TIME + 2)
    assert slot.day == MONDAY
    assert slot.start_hour == START_TIME
    assert slot.end_hour == START_TIME + 2


def test_rejects_non_school_day():
    with pytest.raises(ValueError):
        TimeSlot(SATURDAY, 9, 11)


@pytest.mark.parametrize(
    "start_hour, end_hour",
    [
        (START_TIME - 1, START_TIME + 1),  # starts before the day opens
        (END_TIME - 1, END_TIME + 1),  # ends after the day closes
        (10, 10),  # zero-length
        (11, 10),  # inverted
    ],
)
def test_rejects_invalid_hour_ranges(start_hour, end_hour):
    with pytest.raises(ValueError):
        TimeSlot(MONDAY, start_hour, end_hour)


def test_boundary_hours_are_allowed():
    TimeSlot(MONDAY, START_TIME, END_TIME)


def test_overlap_on_same_day():
    a = TimeSlot(MONDAY, 9, 11)
    b = TimeSlot(MONDAY, 10, 12)
    assert a.overlaps(b)
    assert b.overlaps(a)


def test_back_to_back_slots_do_not_overlap():
    a = TimeSlot(MONDAY, 9, 11)
    b = TimeSlot(MONDAY, 11, 13)
    assert not a.overlaps(b)


def test_different_days_never_overlap():
    a = TimeSlot(MONDAY, 9, 11)
    b = TimeSlot(TUESDAY, 9, 11)
    assert not a.overlaps(b)


def test_equality_is_value_based():
    assert TimeSlot(MONDAY, 9, 11) == TimeSlot(MONDAY, 9, 11)
    assert TimeSlot(MONDAY, 9, 11) != TimeSlot(MONDAY, 9, 12)
