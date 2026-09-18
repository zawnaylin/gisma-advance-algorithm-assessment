from algorithms.graph_engine import GraphColouringSolver
from algorithms.instance import Instance
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup


def make_class(class_id="C0001", students=18, professor_id="P001", duration=1):
    return ClassInformation(class_id, f"Class {class_id}", students, professor_id, duration)


def build(classes, rooms, groups=()):
    professors = [Professor(p) for p in sorted({c.professor_id for c in classes})]
    return Instance(classes, rooms, professors, groups)


def cohort_instance():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=2) for i in range(5)]
    return build(classes, [Room(f"R-{i}", 20) for i in range(5)], [StudentGroup("G-1", classes)])


def test_neighbours_never_share_a_time():
    instance = cohort_instance()
    result = GraphColouringSolver(instance).solve()

    slots = [a.time_slot for a in result.assignments]
    assert result.is_complete
    assert not any(a.overlaps(b) for i, a in enumerate(slots) for b in slots[i + 1:])


def test_highest_degree_class_is_coloured_first():
    # The hub shares a cohort with each of the others, which share nothing with
    # each other: degree 2 against 1 and 1. It is listed last and has the
    # smallest id, so only the degree ordering can put it in the first window.
    a = make_class("C0002", professor_id="P-a")
    b = make_class("C0003", professor_id="P-b")
    hub = make_class("C0001", professor_id="P-hub")
    groups = [StudentGroup("G-1", [hub, a]), StudentGroup("G-2", [hub, b])]
    solver = GraphColouringSolver(build([a, b, hub], [Room("R-1", 20), Room("R-2", 20)], groups))
    solver.solve()
    assigned = solver.slot_map.assigned

    assert assigned["C0001"].start_hour == 9
    assert assigned["C0002"].start_hour == assigned["C0003"].start_hour == 10


def test_slot_map_marks_a_neighbours_window_unsafe():
    a = make_class("C0001")
    b = make_class("C0002")  # same professor, so an edge
    c = make_class("C0003", professor_id="P002")
    solver = GraphColouringSolver(build([a, b, c], [Room("R-1", 20), Room("R-2", 20)]))
    solver.solve()
    slot_map = solver.slot_map

    b_slot = slot_map.assigned["C0002"]
    assert slot_map.unsafe["C0001"][b_slot] == {"C0002"}
    assert slot_map.assigned["C0001"] in slot_map.safe["C0001"]
    # C0003 has no neighbours, so nothing is ever unsafe for it.
    assert slot_map.unsafe["C0003"] == {}
    assert slot_map.safe_count("C0003") == 40


def test_slot_map_finds_a_class_with_no_safe_window():
    # 21 two-hour classes in one cohort need 42h of a 40h week, so one of them
    # is left with every window taken by a neighbour.
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}", duration=2) for i in range(21)]
    instance = build(classes, [Room(f"R-{i}", 20) for i in range(3)], [StudentGroup("G-1", classes)])
    solver = GraphColouringSolver(instance)
    result = solver.solve()

    boxed_in = solver.slot_map.without_safe_slot()
    assert [c.class_info.id for c in result.conflicts] == boxed_in
    assert "1 class(es) have no safe window" in solver.slot_map.summary()


def test_slot_map_renders_the_week():
    solver = GraphColouringSolver(cohort_instance())
    solver.solve()
    grid = solver.slot_map.render("C0000")

    assert grid.count("#") == 1
    assert "x" in grid
    assert grid.splitlines()[1].strip().startswith("Mon")
