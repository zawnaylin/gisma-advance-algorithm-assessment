from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance
from algorithms.solver import (
    GROUP_CONTENTION,
    NO_ROOM_LARGE_ENOUGH,
    PROFESSOR_CONTENTION,
    PROFESSOR_OVERLOADED,
    ROOM_CONTENTION,
)
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup


def make_class(class_id="C0001", students=18, professor_id="P001", duration=1):
    return ClassInformation(class_id, f"Class {class_id}", students, professor_id, duration)


def build(classes, rooms, groups=()):
    professors = [Professor(p) for p in sorted({c.professor_id for c in classes})]
    return Instance(classes, rooms, professors, groups)


def solve(classes, rooms, groups=()):
    return GreedySolver(build(classes, rooms, groups)).solve()


def test_places_a_single_class():
    result = solve([make_class()], [Room("R-1", 20)])

    assert result.is_complete
    assert result.coverage == 1.0
    assert len(result.assignments) == 1


def test_assigned_slot_matches_the_class_duration():
    result = solve([make_class(duration=3)], [Room("R-1", 20)])
    slot = result.assignments[0].time_slot

    assert slot.end_hour - slot.start_hour == 3


def test_best_fit_prefers_the_smallest_adequate_room():
    result = solve([make_class(students=18)], [Room("R-big", 200), Room("R-snug", 20)])

    assert result.assignments[0].room.id == "R-snug"


def test_a_class_too_big_for_every_room_is_structural():
    result = solve([make_class(students=500)], [Room("R-1", 20)])

    conflict = result.conflicts[0]
    assert conflict.cause == NO_ROOM_LARGE_ENOUGH
    assert conflict.is_structural
    assert "500 seats" in conflict.detail


def test_a_professor_booked_beyond_the_week_is_structural():
    # 21 three-hour classes is 63h of teaching in a 40h week.
    classes = [make_class(f"C{i:04d}", duration=3) for i in range(21)]
    result = solve(classes, [Room("R-1", 20) for _ in range(20)])

    overloaded = [c for c in result.conflicts if c.cause == PROFESSOR_OVERLOADED]
    assert overloaded
    assert all(c.is_structural for c in overloaded)
    assert "63h" in overloaded[0].detail


def test_room_contention_is_not_structural():
    # A single room fits two 3h classes a day, so ten in a week. Twelve classes
    # with distinct professors leave the room as the only thing in short supply.
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=3) for i in range(12)]
    result = solve(classes, [Room("R-1", 20)])

    conflict = result.conflicts[0]
    assert conflict.cause == ROOM_CONTENTION
    assert not conflict.is_structural
    assert "the only room that fits" in conflict.detail


def test_professor_contention_is_reported():
    # One professor, 3h classes, plenty of rooms: 14 classes need 42h of a 40h
    # week, so the professor's own timetable is what runs out.
    classes = [make_class(f"C{i:04d}", duration=3) for i in range(13)]
    result = solve(classes, [Room(f"R-{i}", 20) for i in range(10)])

    assert result.conflicts
    assert result.conflicts[0].cause == PROFESSOR_CONTENTION
    assert not result.conflicts[0].is_structural


def test_group_contention_is_reported():
    # Distinct professors and rooms, but every class sits in one cohort, so the
    # cohort's own 40h week is the binding constraint.
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=3) for i in range(14)]
    group = StudentGroup("G-1", classes)
    result = solve(classes, [Room(f"R-{i}", 20) for i in range(10)], groups=[group])

    assert result.conflicts
    assert result.conflicts[0].cause == GROUP_CONTENTION
    assert not result.conflicts[0].is_structural


def test_coverage_and_conflict_split():
    classes = [make_class("C0001"), make_class("C0002", students=500, professor_id="P002")]
    result = solve(classes, [Room("R-1", 20)])

    assert result.coverage == 0.5
    assert not result.is_complete
    assert len(result.structural_conflicts) == 1
    assert result.contention_conflicts == []


def test_report_names_every_cause():
    classes = [make_class("C0001"), make_class("C0002", students=500, professor_id="P002")]
    report = solve(classes, [Room("R-1", 20)]).report(title="scenario-x")

    assert "scenario-x" in report
    assert "1 structural" in report
    assert NO_ROOM_LARGE_ENOUGH in report


def test_report_says_so_when_nothing_conflicts():
    assert "no conflicts" in solve([make_class()], [Room("R-1", 20)]).report()


def test_schedule_is_consistent_with_the_assignments():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}") for i in range(5)]
    result = solve(classes, [Room("R-1", 20)])

    for assignment in result.assignments:
        assert result.schedule.assignment_for(assignment.class_info.id) is assignment
        assert not result.schedule.check_room_available(assignment.room, assignment.time_slot)


def test_no_capacity_deficit_when_the_estate_is_ample():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}") for i in range(4)]
    result = solve(classes, [Room(f"R-{i}", 20) for i in range(4)])

    assert result.capacity_deficits == []


def test_capacity_deficit_is_found_when_a_tier_is_oversubscribed():
    # 30 three-hour classes want 90h from one room that offers 40h a week.
    # Each class fits, so no per-class check can see the shortfall.
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=3) for i in range(30)]
    result = solve(classes, [Room("R-1", 20)])

    deficit = result.capacity_deficits[0]
    assert deficit.capacity == 20
    assert deficit.demand_hours == 90
    assert deficit.supply_hours == 40
    assert deficit.shortfall_hours == 50
    assert "at least 50h cannot be placed" in str(deficit)


def test_deficit_ignores_classes_that_fit_nowhere():
    # The oversized class is reported per class, so counting it again in the
    # tier demand would double-report the same problem.
    classes = [make_class("C0001", students=900), make_class("C0002", professor_id="P002")]
    result = solve(classes, [Room("R-1", 20)])

    assert result.capacity_deficits == []
    assert result.conflicts[0].cause == NO_ROOM_LARGE_ENOUGH


def test_deficit_appears_in_the_report():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=3) for i in range(30)]
    report = solve(classes, [Room("R-1", 20)]).report()

    assert "STRUCTURAL capacity shortfall" in report
