from calendar import MONDAY, TUESDAY

import pytest

from data.room import Room
from data.time_slot import TimeSlot


def test_rejects_non_positive_capacity():
    with pytest.raises(ValueError):
        Room("R-1", 0)
    with pytest.raises(ValueError):
        Room("R-1", -5)


@pytest.mark.parametrize("students, capacity, expected", [(20, 20, True), (21, 20, False), (0, 20, True)])
def test_has_capacity(students, capacity, expected):
    room = Room("R-1", capacity)
    assert room.has_capacity(students) is expected


def test_room_starts_fully_available():
    room = Room("R-1", 20)
    assert room.is_available(TimeSlot(MONDAY, 9, 11))


def test_assigning_blocks_overlapping_slot():
    room = Room("R-1", 20)
    room.assign(TimeSlot(MONDAY, 9, 11))

    assert not room.is_available(TimeSlot(MONDAY, 10, 12))
    with pytest.raises(ValueError):
        room.assign(TimeSlot(MONDAY, 10, 12))


def test_assigning_allows_non_overlapping_slots():
    room = Room("R-1", 20)
    room.assign(TimeSlot(MONDAY, 9, 11))
    room.assign(TimeSlot(MONDAY, 11, 13))
    room.assign(TimeSlot(TUESDAY, 9, 11))

    assert len(room.assigned_slots) == 3
