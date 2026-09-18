"""The four stages are interchangeable solvers, so most of this runs them all."""

import pytest

from algorithms.backtracker import BacktrackingSolver
from algorithms.graph_engine import GraphColouringSolver
from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance
from algorithms.room_allocator import RoomAllocator
from algorithms.solver import SolveResult, Solver
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup

SOLVERS = (GreedySolver, GraphColouringSolver, RoomAllocator, BacktrackingSolver)


def make_class(class_id="C0001", students=18, professor_id="P001", duration=1):
    return ClassInformation(class_id, f"Class {class_id}", students, professor_id, duration)


def build(classes, rooms, groups=()):
    professors = [Professor(p) for p in sorted({c.professor_id for c in classes})]
    return Instance(classes, rooms, professors, groups)


def simple_instance():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}") for i in range(6)]
    return build(classes, [Room("R-1", 20), Room("R-2", 30)])


@pytest.mark.parametrize("solver_class", SOLVERS)
def test_every_solver_satisfies_the_protocol(solver_class):
    solver = solver_class(simple_instance())

    assert isinstance(solver, Solver)
    assert isinstance(solver.name, str) and solver.name


@pytest.mark.parametrize("solver_class", SOLVERS)
def test_every_solver_returns_a_usable_result(solver_class):
    result = solver_class(simple_instance()).solve()

    assert isinstance(result, SolveResult)
    assert result.solver == solver_class(simple_instance()).name
    assert result.is_complete
    assert result.coverage == 1.0
    assert "placed 6 of 6" in result.report()


@pytest.mark.parametrize("solver_class", SOLVERS)
def test_every_solver_reports_an_impossible_class(solver_class):
    classes = [make_class("C0001", students=900), make_class("C0002", professor_id="P002")]
    result = solver_class(build(classes, [Room("R-1", 20)])).solve()

    assert len(result.structural_conflicts) == 1
    assert result.structural_conflicts[0].class_info.id == "C0001"


@pytest.mark.parametrize("solver_class", SOLVERS)
def test_every_solver_keeps_its_schedule_consistent(solver_class):
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=2) for i in range(8)]
    result = solver_class(build(classes, [Room("R-1", 20), Room("R-2", 20)])).solve()

    for assignment in result.assignments:
        assert result.schedule.assignment_for(assignment.class_info.id) is assignment
        assert not result.schedule.check_room_available(assignment.room, assignment.time_slot)


def test_backtracking_recovers_what_greedy_strands():
    """One 3h class and a pile of 1h ones share a single room. Greedy fills the
    early hours with short classes and leaves no 3h window; ejecting a couple of
    them makes room.
    """
    classes = [make_class("C-long", professor_id="P-long", duration=3)]
    classes += [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=1) for i in range(40)]
    instance = build(classes, [Room("R-1", 20)])

    greedy = GreedySolver(instance).solve()
    backtracking = BacktrackingSolver(instance).solve()

    assert backtracking.coverage >= greedy.coverage


def test_graph_has_an_edge_for_a_shared_professor():
    a, b = make_class("C0001"), make_class("C0002")  # both P001
    c = make_class("C0003", professor_id="P002")
    graph = GraphColouringSolver(build([a, b, c], [Room("R-1", 20)])).build_graph()

    assert graph["C0001"] == {"C0002"}
    assert graph["C0003"] == set()


def test_graph_has_an_edge_for_a_shared_cohort():
    a = make_class("C0001", professor_id="P001")
    b = make_class("C0002", professor_id="P002")
    group = StudentGroup("G-1", [a, b])
    graph = GraphColouringSolver(build([a, b], [Room("R-1", 20)], [group])).build_graph()

    assert graph["C0001"] == {"C0002"}


def test_graph_never_links_a_class_to_itself():
    a = make_class("C0001")
    graph = GraphColouringSolver(build([a], [Room("R-1", 20)])).build_graph()

    assert graph["C0001"] == set()


def test_backtracking_flags_what_it_cannot_place_for_manual_intervention():
    classes = [make_class("C0001", students=900), make_class("C0002", professor_id="P002")]
    result = BacktrackingSolver(build(classes, [Room("R-1", 20)])).solve()

    flagged = result.flagged_for_manual_intervention
    assert [c.class_info.id for c in flagged] == ["C0001"]
    report = result.manual_intervention_report()
    assert "FLAGGED FOR MANUAL INTERVENTION: 1 class(es)" in report
    assert "C0001" in report and "split the class" in report


def test_backtracking_never_ends_with_more_conflicts_than_its_first_pass():
    classes = [make_class("C-long", professor_id="P-long", duration=3)]
    classes += [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=1) for i in range(45)]
    result = BacktrackingSolver(build(classes, [Room("R-1", 20)])).solve()

    assert len(result.conflicts) <= result.stats["unplaced_after_first_pass"]


def test_nothing_flagged_when_everything_is_placed():
    result = BacktrackingSolver(simple_instance()).solve()

    assert result.flagged_for_manual_intervention == []
    assert "nothing flagged" in result.manual_intervention_report()
