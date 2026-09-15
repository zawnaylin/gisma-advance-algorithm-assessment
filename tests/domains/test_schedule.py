from calendar import MONDAY, TUESDAY

import pytest

from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.schedule import Schedule
from domains.student_group import StudentGroup
from domains.time_slot import TimeSlot


def make_class(class_id="C0001", students=18, professor_id="P001"):
    return ClassInformation(class_id, f"Class {class_id}", number_of_students=students, professor_id=professor_id)


def test_valid_assignment_has_no_violations():
    schedule = Schedule()
    class_info = make_class()
    room = Room("R-1", 20)
    professor = Professor("P001")
    slot = TimeSlot(MONDAY, 9, 11)

    assert schedule.validate(class_info, room, professor, slot) == []
    assignment = schedule.add_assignment(class_info, room, professor, slot)

    assert schedule.assignment_for("C0001") is assignment
    assert schedule.slots_for_room(room) == (slot,)
    assert schedule.slots_for_professor(professor) == (slot,)


def test_over_capacity_is_flagged_and_blocked():
    schedule = Schedule()
    class_info = make_class(students=25)
    room = Room("R-1", 20)
    professor = Professor("P001")
    slot = TimeSlot(MONDAY, 9, 11)

    violations = schedule.validate(class_info, room, professor, slot)
    assert len(violations) == 1
    assert "capacity" in violations[0]

    with pytest.raises(ValueError):
        schedule.add_assignment(class_info, room, professor, slot)


def test_room_double_booking_is_flagged():
    schedule = Schedule()
    room = Room("R-1", 20)
    professor_a = Professor("P001")
    professor_b = Professor("P002")
    slot_a = TimeSlot(MONDAY, 9, 11)
    slot_b = TimeSlot(MONDAY, 10, 12)

    schedule.add_assignment(make_class("C0001", professor_id="P001"), room, professor_a, slot_a)

    violations = schedule.validate(make_class("C0002", professor_id="P002"), room, professor_b, slot_b)
    assert any("already booked" in v for v in violations)


def test_professor_double_booking_is_flagged_across_rooms():
    schedule = Schedule()
    professor = Professor("P001")
    room_a = Room("R-1", 20)
    room_b = Room("R-2", 20)
    slot_a = TimeSlot(MONDAY, 9, 11)
    slot_b = TimeSlot(MONDAY, 10, 12)

    schedule.add_assignment(make_class("C0001"), room_a, professor, slot_a)

    violations = schedule.validate(make_class("C0002"), room_b, professor, slot_b)
    assert any("already teaching" in v for v in violations)


def test_student_group_conflict_is_flagged_even_in_different_rooms():
    schedule = Schedule()
    class_a = make_class("C0001", professor_id="P001")
    class_b = make_class("C0002", professor_id="P002")
    group = StudentGroup("G-1", [class_a, class_b])

    room_a = Room("R-1", 20)
    room_b = Room("R-2", 20)
    professor_a = Professor("P001")
    professor_b = Professor("P002")

    slot_a = TimeSlot(MONDAY, 9, 11)
    slot_b = TimeSlot(MONDAY, 10, 12)

    schedule.add_assignment(class_a, room_a, professor_a, slot_a, groups=[group])

    violations = schedule.validate(class_b, room_b, professor_b, slot_b, groups=[group])
    assert any("conflicting class" in v for v in violations)


def test_multiple_violations_are_all_reported():
    schedule = Schedule()
    room = Room("R-1", 10)
    professor = Professor("P001")
    slot = TimeSlot(MONDAY, 9, 11)

    schedule.add_assignment(make_class("C0001", students=5), room, professor, slot)

    overloaded_class = make_class("C0002", students=50, professor_id="P001")
    violations = schedule.validate(overloaded_class, room, professor, slot)

    assert len(violations) == 3


def test_non_overlapping_slots_share_a_room():
    schedule = Schedule()
    room = Room("R-1", 20)
    schedule.add_assignment(make_class("C0001", professor_id="P001"), room, Professor("P001"), TimeSlot(MONDAY, 9, 11))
    schedule.add_assignment(make_class("C0002", professor_id="P002"), room, Professor("P002"), TimeSlot(MONDAY, 11, 13))
    schedule.add_assignment(make_class("C0003", professor_id="P003"), room, Professor("P003"), TimeSlot(TUESDAY, 9, 11))

    assert len(schedule.slots_for_room(room)) == 3


def test_scheduling_the_same_class_twice_is_rejected():
    schedule = Schedule()
    room = Room("R-1", 20)
    professor = Professor("P001")
    schedule.add_assignment(make_class("C0001"), room, professor, TimeSlot(MONDAY, 9, 11))

    with pytest.raises(ValueError):
        schedule.add_assignment(make_class("C0001"), room, professor, TimeSlot(TUESDAY, 9, 11))


def test_unassign_frees_the_room_and_the_professor():
    schedule = Schedule()
    room = Room("R-1", 20)
    professor = Professor("P001")
    slot = TimeSlot(MONDAY, 9, 11)
    schedule.add_assignment(make_class("C0001"), room, professor, slot)

    removed = schedule.unassign("C0001")

    assert removed.class_info.id == "C0001"
    assert schedule.assignment_for("C0001") is None
    assert schedule.assignments == []
    assert schedule.check_room_available(room, slot)
    assert schedule.check_professor_available(professor, slot)
    assert schedule.slots_for_room(room) == ()
    assert schedule.slots_for_professor(professor) == ()


def test_unassign_frees_the_student_group():
    schedule = Schedule()
    class_a = make_class("C0001", professor_id="P001")
    class_b = make_class("C0002", professor_id="P002")
    group = StudentGroup("G-1", [class_a, class_b])
    slot = TimeSlot(MONDAY, 9, 11)

    schedule.add_assignment(class_a, Room("R-1", 20), Professor("P001"), slot, groups=[group])
    assert not schedule.check_group_available(group, slot)

    schedule.unassign("C0001")
    assert schedule.check_group_available(group, slot)


def test_unassign_is_a_no_op_for_an_unscheduled_class():
    assert Schedule().unassign("C9999") is None


def test_unassign_only_frees_the_slot_it_owns():
    schedule = Schedule()
    room = Room("R-1", 20)
    kept = TimeSlot(MONDAY, 9, 11)
    dropped = TimeSlot(MONDAY, 11, 13)
    schedule.add_assignment(make_class("C0001", professor_id="P001"), room, Professor("P001"), kept)
    schedule.add_assignment(make_class("C0002", professor_id="P002"), room, Professor("P002"), dropped)

    schedule.unassign("C0002")

    assert schedule.slots_for_room(room) == (kept,)
    assert not schedule.check_room_available(room, kept)
    assert schedule.check_room_available(room, dropped)


def test_place_retreat_replace_round_trip():
    """The invariant a backtracker depends on: undoing a placement must leave
    the schedule exactly as it was, so the next branch starts from clean state.
    """
    schedule = Schedule()
    class_info = make_class("C0001")
    room = Room("R-1", 20)
    professor = Professor("P001")
    first = TimeSlot(MONDAY, 9, 11)
    second = TimeSlot(TUESDAY, 14, 16)

    schedule.add_assignment(class_info, room, professor, first)
    schedule.unassign("C0001")

    assert schedule.assignments == []
    assert schedule.slots_for_room(room) == ()
    assert schedule.validate(class_info, room, professor, first) == []

    schedule.add_assignment(class_info, room, professor, second)
    assert schedule.assignment_for("C0001").time_slot == second
    assert schedule.check_room_available(room, first)
