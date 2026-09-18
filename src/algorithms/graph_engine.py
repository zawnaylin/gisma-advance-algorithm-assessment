"""Stage 2 - graph colouring, the "collision" engine.

Two classes cannot run at the same time when they share a professor or a
cohort. Draw a node per class and an edge for every such pair, and the
timetable becomes a colouring problem: neighbours need different colours, and
the colours are time slots. Collisions are ruled out before they happen,
because a class is only ever offered the slots its neighbours have left free.

The colouring is Welsh-Powell: sort the classes once by degree, highest first -
the class that collides with the most others is the hardest to fit - and give
each the first colour none of its neighbours is using. (Walking colour by colour
and sweeping the sorted list, as the textbook states it, yields the same
colouring as this vertex-by-vertex first fit.)

Durations make this colouring by analogy rather than by the letter: slots have
different lengths, so two neighbours can clash without sharing a slot exactly.
"Different colour" is read as "non-overlapping slot".

A colour is only useful if a room is free in it, so each class is also given a
provisional room here. Stage 3 keeps the time slots fixed and redoes the rooms.

The by-product is a `SlotMap`: for every class, which of its candidate windows
are safe (no neighbour there) and which are unsafe, and which neighbours make
them so.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from domains.constraints import AVAILABLE_DAY, END_TIME, START_TIME
from domains.schedule import Schedule
from domains.time_slot import TimeSlot

from algorithms.instance import Instance
from algorithms.solver import SolveResult

DAY_NAMES = {day: name for day, name in zip(AVAILABLE_DAY, ("Mon", "Tue", "Wed", "Thu", "Fri"))}


@dataclass
class SlotMap:
    """Safe versus unsafe time slots, per class, after colouring.

    A window is unsafe for a class when a neighbour in the conflict graph
    (same professor or shared cohort) was placed in an overlapping window.
    Rooms play no part here: this is purely the collision structure.
    """

    assigned: Dict[str, TimeSlot] = field(default_factory=dict)
    safe: Dict[str, List[TimeSlot]] = field(default_factory=dict)
    unsafe: Dict[str, Dict[TimeSlot, Set[str]]] = field(default_factory=dict)

    def safe_count(self, class_id: str) -> int:
        return len(self.safe.get(class_id, ()))

    def unsafe_count(self, class_id: str) -> int:
        return len(self.unsafe.get(class_id, {}))

    def without_safe_slot(self) -> List[str]:
        """Classes every one of whose windows collides with a neighbour."""
        return sorted(cid for cid in self.safe if not self.safe[cid])

    def summary(self) -> str:
        total_safe = sum(len(s) for s in self.safe.values())
        total_unsafe = sum(len(u) for u in self.unsafe.values())
        windows = total_safe + total_unsafe
        share = total_safe / windows if windows else 1.0
        boxed_in = self.without_safe_slot()
        return (
            f"{total_safe} of {windows} class-windows are safe ({share:.1%}); "
            f"{len(boxed_in)} class(es) have no safe window at all"
        )

    def render(self, class_id: str) -> str:
        """The week as a grid of start hours for one class.

        `#` its own slot, `.` safe, `x` unsafe (a neighbour is there).
        """
        assigned = self.assigned.get(class_id)
        by_start: Dict[tuple, str] = {}
        for slot in self.safe.get(class_id, ()):
            by_start[(slot.day, slot.start_hour)] = "."
        for slot in self.unsafe.get(class_id, {}):
            by_start[(slot.day, slot.start_hour)] = "x"
        if assigned is not None:
            by_start[(assigned.day, assigned.start_hour)] = "#"

        hours = range(START_TIME, END_TIME)
        lines = ["      " + " ".join(f"{h:>2}" for h in hours)]
        for day in AVAILABLE_DAY:
            cells = " ".join(f"{by_start.get((day, h), ' '):>2}" for h in hours)
            lines.append(f"  {DAY_NAMES[day]} {cells}")
        return "\n".join(lines)


class GraphColouringSolver:
    name = "graph-welsh-powell"

    def __init__(self, instance: Instance):
        self.instance = instance
        self.slot_map = SlotMap()

    def build_graph(self) -> Dict[str, Set[str]]:
        """Adjacency by class id. An edge means 'cannot share a time slot'."""
        instance = self.instance
        adjacency: Dict[str, Set[str]] = {c.id: set() for c in instance.classes}

        by_professor: Dict[str, List[str]] = {}
        for class_info in instance.classes:
            by_professor.setdefault(class_info.professor_id, []).append(class_info.id)
        for taught in by_professor.values():
            for class_id in taught:
                adjacency[class_id].update(taught)

        for class_info in instance.classes:
            adjacency[class_info.id].update(instance.peers(class_info))

        for class_id in adjacency:
            adjacency[class_id].discard(class_id)
        return adjacency

    def solve(self) -> SolveResult:
        instance = self.instance
        adjacency = self.build_graph()
        schedule = Schedule()

        by_id = {c.id: c for c in instance.classes}
        placed_slots: Dict[str, TimeSlot] = {}
        conflicts_pending = []

        # Welsh-Powell order: highest degree first. Duration and head count
        # break ties, and the id last makes the order the same on every run.
        order = sorted(
            by_id,
            key=lambda cid: (
                len(adjacency[cid]),
                by_id[cid].duration_hours,
                by_id[cid].number_of_students,
                cid,
            ),
            reverse=True,
        )

        for class_id in order:
            class_info = by_id[class_id]
            slot = self._place(schedule, class_info)
            if slot is None:
                conflicts_pending.append(class_info)
            else:
                placed_slots[class_id] = slot

        self.slot_map = self._build_slot_map(adjacency, placed_slots)

        edges = sum(len(n) for n in adjacency.values()) // 2
        result = SolveResult(
            solver=self.name,
            schedule=schedule,
            assignments=schedule.assignments,
            capacity_deficits=instance.capacity_deficits(),
            stats={
                "nodes": len(adjacency),
                "edges": edges,
                "max_degree": max((len(n) for n in adjacency.values()), default=0),
                "slots_used": len(set(placed_slots.values())),
            },
        )
        for class_info in conflicts_pending:
            result.conflicts.append(instance.diagnose(schedule, class_info))
        return result

    def _place(self, schedule: Schedule, class_info):
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        # Goal 4 is weighed here, where the time slot is chosen: a right-sized
        # room at a later time beats an oversized room now.
        for time_slot, room in self.instance.placements(class_info, avoid_oversized=True):
            if schedule.validate(class_info, room, professor, time_slot, groups):
                continue
            schedule.add_assignment(class_info, room, professor, time_slot, groups)
            return time_slot
        return None

    def _build_slot_map(
        self, adjacency: Dict[str, Set[str]], placed_slots: Dict[str, TimeSlot]
    ) -> SlotMap:
        slot_map = SlotMap(assigned=dict(placed_slots))
        for class_info in self.instance.classes:
            neighbour_slots = [
                (n, placed_slots[n]) for n in adjacency[class_info.id] if n in placed_slots
            ]
            safe: List[TimeSlot] = []
            unsafe: Dict[TimeSlot, Set[str]] = {}
            for slot in self.instance.candidate_slots(class_info):
                clashes = {n for n, other in neighbour_slots if slot.overlaps(other)}
                if clashes:
                    unsafe[slot] = clashes
                else:
                    safe.append(slot)
            slot_map.safe[class_info.id] = safe
            slot_map.unsafe[class_info.id] = unsafe
        return slot_map
