"""Stage 3 - dynamic programming, the "efficiency" engine.

Stage 2 fixes when every class runs. This stage keeps those times exactly and
decides only where: it reassigns rooms so that the total number of empty seats
is as small as it can be, without ever putting a class in a room too small for
it or two classes in one room at once.

The week is solved one time slot at a time - each day is swept hour by hour,
and at each hour the classes that start then are given rooms from those not
still occupied by a class that started earlier. That per-slot problem is a
minimum-waste matching of n classes to m free rooms, solved by DP:

    sort classes by size    s_1 <= s_2 <= ... <= s_n
    sort free rooms by size c_1 <= c_2 <= ... <= c_m

    state       W[i][j] = least waste seating the i smallest classes using only
                          the j smallest rooms (infinity if impossible)
    base        W[0][j] = 0          W[i][0] = infinity for i > 0
    recurrence  W[i][j] = min( W[i][j-1],                         room j unused
                               W[i-1][j-1] + c_j - s_i  if c_j >= s_i )  room j to class i
    answer      W[n][m], and the choices are recovered by walking the table back

Why the sorted order is safe to assume: if a smaller class sits in a bigger
room than a larger class, swapping the two keeps both feasible (each room still
holds its class) and leaves the waste unchanged (the same rooms are in use). So
some optimal allocation never crosses, and the DP only has to consider those.
That is n*m table cells instead of the m!/(m-n)! ways of handing out rooms -
for 10 classes and 50 rooms, 500 cells instead of about 3.7 * 10^16 allocations.

A sweep that is optimal slot by slot is not guaranteed optimal for the whole
day, because a room chosen at 9:00 is still busy at 10:00. Each day is
therefore checked against the rooms it came in with, and kept only if it wastes
no more - so this stage never makes a schedule worse.
"""

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
    """Seat every class in its own room with the fewest empty seats in total.

    Returns (waste, {class id: room}), or None when the rooms cannot hold every
    class at once.
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
    name = "dp-rooms"

    def __init__(self, instance: Instance, seed=None):
        self.instance = instance
        self.seed = seed if seed is not None else GraphColouringSolver(instance)

    def solve(self) -> SolveResult:
        return self.allocate(self.seed.solve())

    def allocate(self, result: SolveResult) -> SolveResult:
        """Reassign rooms in a finished schedule, keeping every time slot."""
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

        # Rebuilding through Schedule re-checks every hard constraint, so a
        # mistake here fails loudly instead of producing a double booking.
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
        """Sweep one day hour by hour; None if some hour cannot be seated."""
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
    return room.capacity - class_info.number_of_students
