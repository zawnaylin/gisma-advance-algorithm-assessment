from calendar import MONDAY, TUESDAY

import pytest

from data.professor import Professor
from data.time_slot import TimeSlot


def test_professor_starts_fully_available():
    professor = Professor("P001", "Dr. Turing")
    assert professor.is_available(TimeSlot(MONDAY, 9, 11))


def test_assigning_blocks_overlapping_slot():
    professor = Professor("P001")
    professor.assign(TimeSlot(MONDAY, 9, 11))

    assert not professor.is_available(TimeSlot(MONDAY, 10, 12))
    with pytest.raises(ValueError):
        professor.assign(TimeSlot(MONDAY, 10, 12))


def test_assigning_allows_non_overlapping_slots():
    professor = Professor("P001")
    professor.assign(TimeSlot(MONDAY, 9, 11))
    professor.assign(TimeSlot(TUESDAY, 9, 11))

    assert len(professor.assigned_slots) == 2
