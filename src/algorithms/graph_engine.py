"""Stage 2: Welsh-Powell graph colouring and the safe/unsafe slot map."""

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
    """For each class, which candidate time slots are safe and which clash with a neighbour.

    Attributes:
        assigned: the slot each placed class received.
        safe: candidate slots with no neighbour in an overlapping slot.
        unsafe: candidate slots that clash, with the ids of the clashing neighbours.
    """

    assigned: Dict[str, TimeSlot] = field(default_factory=dict)
    safe: Dict[str, List[TimeSlot]] = field(default_factory=dict)
    unsafe: Dict[str, Dict[TimeSlot, Set[str]]] = field(default_factory=dict)

    def safe_count(self, class_id: str) -> int:
        """Number of safe slots for the class."""
        return len(self.safe.get(class_id, ()))

    def unsafe_count(self, class_id: str) -> int:
        """Number of unsafe slots for the class."""
        return len(self.unsafe.get(class_id, {}))

    def without_safe_slot(self) -> List[str]:
        """Ids of the classes with no safe slot."""
        return sorted(cid for cid in self.safe if not self.safe[cid])

    def summary(self) -> str:
        """One line: share of safe slots, and how many classes have none."""
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
        """Render the class's week as a grid of start hours.

        `#` marks its own slot, `.` a safe slot and `x` an unsafe one.
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
    """Colours the conflict graph with time slots in Welsh-Powell order.

    After `solve()`, `slot_map` holds the safe/unsafe map for every class.
    """

    name = "graph-welsh-powell"

    def __init__(self, instance: Instance):
        self.instance = instance
        self.slot_map = SlotMap()

    def build_graph(self) -> Dict[str, Set[str]]:
        """Conflict graph as adjacency sets: an edge joins two classes that share
        a professor or a student group."""
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
        """Give each class, highest degree first, the first time slot free of its neighbours."""
        instance = self.instance
        adjacency = self.build_graph()
        schedule = Schedule()

        by_id = {c.id: c for c in instance.classes}
        placed_slots: Dict[str, TimeSlot] = {}
        conflicts_pending = []

        # Highest degree first; ties by duration, head count, then id.
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
        """Book the first valid placement, preferring right-sized rooms; returns
        the chosen slot, or None."""
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        for time_slot, room in self.instance.placements(class_info, avoid_oversized=True):
            if schedule.validate(class_info, room, professor, time_slot, groups):
                continue
            schedule.add_assignment(class_info, room, professor, time_slot, groups)
            return time_slot
        return None

    def _build_slot_map(
        self, adjacency: Dict[str, Set[str]], placed_slots: Dict[str, TimeSlot]
    ) -> SlotMap:
        """Classify every candidate slot of every class as safe or unsafe."""
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
