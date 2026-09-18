"""The four goals of the brief, checked on schedules built by hand and by every stage."""

import pytest

from algorithms.audit import audit
from algorithms.backtracker import BacktrackingSolver
from algorithms.graph_engine import GraphColouringSolver
from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance, is_oversized
from algorithms.room_allocator import RoomAllocator
from data.assignment import ClassAssignment
from data.loader import load_scenario
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup
from domains.time_slot import TimeSlot

SOLVERS = (GreedySolver, GraphColouringSolver, RoomAllocator, BacktrackingSolver)
MONDAY_9 = TimeSlot(0, 9, 11)


def build(classes, rooms, groups=()):
    professors = [Professor(p) for p in sorted({c.professor_id for c in classes})]
    return Instance(classes, rooms, professors, groups)


def brief_example():
    """Group A (Year 1 CS) needs both Intro to Math and Intro to Programming.
    Different professors, plenty of rooms - only the shared students connect them."""
    math = ClassInformation("C-MATH", "Intro to Math", 30, "P-math", 2)
    programming = ClassInformation("C-PROG", "Intro to Programming", 30, "P-cs", 2)
    group_a = StudentGroup("G-CS-Y1", [math, programming], size=30)
    return build([math, programming], [Room("R-1", 40), Room("R-2", 40)], [group_a])


def place(instance, class_id, room_id, slot=MONDAY_9):
    class_info = next(c for c in instance.classes if c.id == class_id)
    room = next(r for r in instance.rooms if r.id == room_id)
    return ClassAssignment(class_info, room, instance.professor_for(class_info), slot)


@pytest.mark.parametrize("solver_class", SOLVERS)
def test_shared_students_keep_classes_apart_even_with_different_professors(solver_class):
    instance = brief_example()
    result = solver_class(instance).solve()

    first, second = (a.time_slot for a in result.assignments)
    assert result.is_complete
    assert not first.overlaps(second)
    assert audit(result.assignments, instance).is_valid


def test_audit_catches_students_in_two_places_at_once():
    instance = brief_example()
    # Separate rooms and professors: nothing but the student group is violated.
    clash = [place(instance, "C-MATH", "R-1"), place(instance, "C-PROG", "R-2")]

    result = audit(clash, instance)

    assert result.student_clashes == [("G-CS-Y1", "C-MATH", "C-PROG")]
    assert result.students_double_booked == 30
    assert result.professor_clashes == [] and result.room_double_bookings == []
    assert not result.is_valid


def test_audit_catches_a_professor_teaching_twice_at_once():
    a = ClassInformation("C1", "A", 10, "P1", 2)
    b = ClassInformation("C2", "B", 10, "P1", 2)
    instance = build([a, b], [Room("R-1", 10), Room("R-2", 10)])

    result = audit([place(instance, "C1", "R-1"), place(instance, "C2", "R-2")], instance)

    assert result.professor_clashes == [("P1", "C1", "C2")]


def test_audit_catches_a_double_booked_room():
    a = ClassInformation("C1", "A", 10, "P1", 2)
    b = ClassInformation("C2", "B", 10, "P2", 2)
    instance = build([a, b], [Room("R-1", 10)])

    result = audit([place(instance, "C1", "R-1"), place(instance, "C2", "R-1")], instance)

    assert result.room_double_bookings == [("R-1", "C1", "C2")]


def test_audit_catches_a_class_that_does_not_fit():
    big = ClassInformation("C1", "Big lecture", 200, "P1", 2)
    instance = build([big], [Room("R-50", 50)])

    result = audit([place(instance, "C1", "R-50")], instance)

    assert [a.class_info.id for a in result.over_capacity] == ["C1"]
    assert not result.is_valid


def test_audit_flags_the_auditorium_for_a_small_seminar_but_it_is_soft():
    seminar = ClassInformation("C1", "Poetry Seminar", 10, "P1", 2)
    instance = build([seminar], [Room("AUD", 500)])

    result = audit([place(instance, "C1", "AUD")], instance)

    assert [a.class_info.id for a in result.oversized] == ["C1"]
    assert result.wasted_seats == 490
    assert result.is_valid  # goal 4 is soft - flagged, not a hard violation


def test_oversized_means_more_than_twice_the_seats_needed():
    seminar = ClassInformation("C1", "Seminar", 10, "P1")

    assert not is_oversized(seminar, Room("R-20", 20))
    assert is_oversized(seminar, Room("R-21", 21))


def test_colouring_moves_a_seminar_to_a_later_slot_rather_than_heat_the_auditorium():
    # A larger, unrelated class takes the snug room at 9:00. Greedy then puts
    # the seminar in the first free room at 9:00 - the auditorium. Stage 2
    # prefers the snug room at 10:00.
    lecture = ClassInformation("C-LEC", "Lecture", 15, "P1", 1)
    seminar = ClassInformation("C-SEM", "Poetry Seminar", 10, "P2", 1)
    instance = build([lecture, seminar], [Room("R-15", 15), Room("AUD", 500)])

    greedy = {a.class_info.id: a for a in GreedySolver(instance).solve().assignments}
    coloured = {a.class_info.id: a for a in GraphColouringSolver(instance).solve().assignments}

    assert greedy["C-SEM"].room.id == "AUD"
    assert coloured["C-SEM"].room.id == "R-15"
    assert coloured["C-SEM"].time_slot.start_hour == 10


def test_university_scenario_matches_the_brief():
    scenario = load_scenario("university")

    assert scenario.students == 5000
    assert len(scenario.professors) == 300
    assert len(scenario.rooms) == 50
    assert max(r.capacity for r in scenario.rooms) == 500


def test_university_head_counts_add_up_from_the_cohorts():
    scenario = load_scenario("university")
    attending = {}
    for group in scenario.groups:
        for class_info in group.classes:
            attending[class_info.id] = attending.get(class_info.id, 0) + group.size

    for class_info in scenario.classes:
        assert class_info.number_of_students == attending[class_info.id], class_info.id


def test_university_contains_the_brief_example():
    scenario = load_scenario("university")
    group = next(g for g in scenario.groups if g.id == "G-CS-Y1-A")
    names = {c.name.split(" (")[0]: c for c in group.classes}

    math, programming = names["Intro to Math"], names["Intro to Programming"]
    assert math.professor_id != programming.professor_id
