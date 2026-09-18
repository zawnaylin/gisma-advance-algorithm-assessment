"""Stage 3: dynamic-programming room allocation on fixed time slots."""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from data.assignment import ClassAssignment
from domains.class_information import ClassInformation
from domains.constraints import END_TIME, START_TIME
from domains.room import Room
from domains.schedule import Schedule

from algorithms.graph_engine import GraphColouringSolver
from algorithms.instance import Instance
from algorithms.solver import SolveResult


def min_waste_allocation(
    classes: Sequence[ClassInformation], rooms: Sequence[Room]
) -> Optional[Tuple[int, Dict[str, Room]]]:
    """Give each class its own room so the total of empty seats is smallest.

    `waste[i][j]` is the least waste seating the i smallest classes in the j
    smallest rooms.

    Args:
        classes: the classes that start in the same time slot.
        rooms: the rooms free for that slot.

    Returns:
        (total waste, {class id: room}), or None if the rooms cannot hold every class.
    """
    classes = sorted(classes, key=lambda c: c.number_of_students)
    rooms = sorted(rooms, key=lambda r: (r.capacity, r.id))
    n, m = len(classes), len(rooms)
    if n > m:
        return None

    waste = [[math.inf] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        waste[0][j] = 0

    for i in range(1, n + 1):
        size = classes[i - 1].number_of_students
        for j in range(1, m + 1):
            best = waste[i][j - 1]
            capacity = rooms[j - 1].capacity
            if capacity >= size:
                best = min(best, waste[i - 1][j - 1] + capacity - size)
            waste[i][j] = best

    if waste[n][m] == math.inf:
        return None

    allocation: Dict[str, Room] = {}
    i, j = n, m
    while i > 0:
        if waste[i][j] == waste[i][j - 1]:
            j -= 1
        else:
            allocation[classes[i - 1].id] = rooms[j - 1]
            i, j = i - 1, j - 1
    return int(waste[n][m]), allocation


class RoomAllocator:
    """Keeps a schedule's time slots and reassigns rooms to minimise wasted seats.

    Args:
        instance: the problem being solved.
        seed: the solver whose time slots are kept; defaults to Stage 2.
    """

    name = "dp-rooms"

    def __init__(self, instance: Instance, seed=None):
        self.instance = instance
        self.seed = seed if seed is not None else GraphColouringSolver(instance)

    def solve(self) -> SolveResult:
        """Run the seed solver, then reallocate its rooms."""
        return self.allocate(self.seed.solve())

    def allocate(self, result: SolveResult) -> SolveResult:
        """Reassign the rooms of a finished schedule, keeping every time slot.

        A day's new rooms are kept only if they waste no more seats than before.

        Args:
            result: the schedule to improve.

        Returns:
            A new result with the same placements and conflicts, and new rooms.
        """
        by_day: Dict[int, List[ClassAssignment]] = {}
        for assignment in result.assignments:
            by_day.setdefault(assignment.time_slot.day, []).append(assignment)

        rooms: Dict[str, Room] = {a.class_info.id: a.room for a in result.assignments}
        slots_solved = 0
        days_kept = 0
        for day_assignments in by_day.values():
            allocated, solved = self._allocate_day(day_assignments)
            slots_solved += solved
            before = sum(_waste(a.class_info, a.room) for a in day_assignments)
            if allocated is None or sum(
                _waste(a.class_info, allocated[a.class_info.id]) for a in day_assignments
            ) > before:
                days_kept += 1
                continue
            rooms.update(allocated)

        # Rebuild through Schedule so every hard constraint is re-checked.
        schedule = Schedule()
        for a in result.assignments:
            schedule.add_assignment(
                a.class_info,
                rooms[a.class_info.id],
                a.professor,
                a.time_slot,
                self.instance.groups_for(a.class_info),
            )

        allocated_result = SolveResult(
            solver=self.name,
            schedule=schedule,
            assignments=schedule.assignments,
            conflicts=list(result.conflicts),
            capacity_deficits=list(result.capacity_deficits),
        )
        allocated_result.stats = {
            "seeded_by": result.solver,
            "slots_solved": slots_solved,
            "days_kept_as_seeded": days_kept,
            "wasted_seats_before": result.wasted_seats,
            "wasted_seats_after": allocated_result.wasted_seats,
        }
        return allocated_result

    def _allocate_day(
        self, assignments: List[ClassAssignment]
    ) -> Tuple[Optional[Dict[str, Room]], int]:
        """Allocate one day's rooms hour by hour, solving each hour with the DP.

        Returns:
            ({class id: room} or None if some hour cannot be seated, hours solved).
        """
        allocation: Dict[str, Room] = {}
        running: List[Tuple[int, Room]] = []  # (end hour, room) of classes already seated
        solved = 0

        for hour in range(START_TIME, END_TIME):
            starting = [a.class_info for a in assignments if a.time_slot.start_hour == hour]
            if not starting:
                continue

            running = [(end, room) for end, room in running if end > hour]
            busy = {room.id for _, room in running}
            free = [room for room in self.instance.rooms if room.id not in busy]

            solution = min_waste_allocation(starting, free)
            solved += 1
            if solution is None:
                return None, solved

            _, chosen = solution
            allocation.update(chosen)
            for class_info in starting:
                running.append((hour + class_info.duration_hours, chosen[class_info.id]))

        return allocation, solved


def _waste(class_info: ClassInformation, room: Room) -> int:
    """Empty seats when the class sits in the room."""
    return room.capacity - class_info.number_of_students
