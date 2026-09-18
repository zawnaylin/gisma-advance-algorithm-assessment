import itertools
import random

from algorithms.graph_engine import GraphColouringSolver
from algorithms.greedy_solver import GreedySolver
from algorithms.instance import Instance
from algorithms.optimizer import RoomAllocator, min_waste_allocation
from algorithms.solver import SolveResult
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.schedule import Schedule
from domains.time_slot import TimeSlot


def make_class(class_id="C0001", students=18, professor_id="P001", duration=1):
    return ClassInformation(class_id, f"Class {class_id}", students, professor_id, duration)


def build(classes, rooms, groups=()):
    professors = [Professor(p) for p in sorted({c.professor_id for c in classes})]
    return Instance(classes, rooms, professors, groups)


def brute_force(classes, rooms):
    """Every way of handing out rooms - what the DP is meant to avoid."""
    best = None
    for chosen in itertools.permutations(rooms, len(classes)):
        if all(c.number_of_students <= r.capacity for c, r in zip(classes, chosen)):
            waste = sum(r.capacity - c.number_of_students for c, r in zip(classes, chosen))
            best = waste if best is None else min(best, waste)
    return best


def test_dp_seats_each_class_in_the_snuggest_combination():
    classes = [make_class("A", 12), make_class("B", 19)]
    rooms = [Room("R-120", 120), Room("R-20", 20), Room("R-15", 15)]

    waste, allocation = min_waste_allocation(classes, rooms)

    assert allocation == {"A": rooms[2], "B": rooms[1]}
    assert waste == 3 + 1


def test_dp_returns_none_when_the_rooms_cannot_hold_everyone():
    assert min_waste_allocation([make_class("A", 30)], [Room("R-20", 20)]) is None
    assert min_waste_allocation([make_class("A"), make_class("B")], [Room("R-1", 20)]) is None


def test_dp_matches_brute_force_on_random_slots():
    rng = random.Random(7)
    for trial in range(200):
        rooms = [Room(f"R{i}", rng.randint(10, 60)) for i in range(rng.randint(1, 6))]
        classes = [make_class(f"C{i}", rng.randint(5, 60)) for i in range(rng.randint(1, len(rooms)))]

        expected = brute_force(classes, rooms)
        solution = min_waste_allocation(classes, rooms)

        if expected is None:
            assert solution is None, trial
            continue
        waste, allocation = solution
        assert waste == expected, trial
        assert len({r.id for r in allocation.values()}) == len(classes)
        assert all(c.fits_in(allocation[c.id]) for c in classes)


def test_allocator_moves_a_class_out_of_an_oversized_room():
    class_info = make_class(students=18)
    rooms = [Room("R-huge", 400), Room("R-snug", 20)]
    instance = build([class_info], rooms)

    schedule = Schedule()
    slot = TimeSlot(0, 9, 10)
    schedule.add_assignment(class_info, rooms[0], instance.professor_for(class_info), slot)
    wasteful = SolveResult("by-hand", schedule, schedule.assignments)

    result = RoomAllocator(instance).allocate(wasteful)

    assert result.assignments[0].room.id == "R-snug"
    assert result.assignments[0].time_slot == slot
    assert result.stats["wasted_seats_before"] == 382
    assert result.stats["wasted_seats_after"] == 2


def test_allocator_keeps_every_time_slot_and_never_adds_waste():
    rng = random.Random(3)
    classes = [
        make_class(f"C{i:04d}", rng.randint(5, 80), f"P{i % 9:03d}", rng.randint(1, 3))
        for i in range(60)
    ]
    rooms = [Room(f"R-{i}", cap) for i, cap in enumerate((15, 20, 25, 30, 40, 60, 80, 120))]
    instance = build(classes, rooms)

    for seed in (GreedySolver(instance), GraphColouringSolver(instance)):
        seeded = seed.solve()
        allocated = RoomAllocator(instance).allocate(seeded)

        slots = {a.class_info.id: a.time_slot for a in seeded.assignments}
        assert {a.class_info.id: a.time_slot for a in allocated.assignments} == slots
        assert allocated.wasted_seats <= seeded.wasted_seats
        assert len(allocated.conflicts) == len(seeded.conflicts)


def test_allocator_reports_which_solver_fixed_the_times():
    classes = [make_class(f"C{i:04d}", professor_id=f"P{i:03d}") for i in range(4)]
    instance = build(classes, [Room("R-1", 20), Room("R-2", 30)])

    assert RoomAllocator(instance).solve().stats["seeded_by"] == "graph-welsh-powell"
    assert RoomAllocator(instance, seed=GreedySolver(instance)).solve().stats["seeded_by"] == "greedy"
