from calendar import MONDAY

import pytest

from data.class_information import ClassInformation
from data.professor import Professor
from data.room import Room
from data.schedule import Schedule
from data.student_group import StudentGroup
from data.time_slot import TimeSlot


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
    assert room.assigned_slots == [slot]
    assert professor.assigned_slots == [slot]


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
