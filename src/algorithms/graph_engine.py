"""Graph colouring.

Two classes cannot run at the same time when they share a professor or a
cohort. Draw a node per class and an edge for every such pair, and the
timetable becomes a colouring problem: neighbours need different colours, and
the colours are time slots.

The ordering is DSATUR's. Instead of fixing the order up front, it repeatedly
picks the class whose neighbours have already used the most distinct slots -
the one with the fewest colours left, so the one most likely to fail if left
until later. Ties go to the highest degree.

Durations make this colouring by analogy rather than by the letter: slots have
different lengths, so two neighbours can clash without sharing a slot exactly.
Saturation is still the right measure of how boxed-in a class is, and feasibility
is checked against the schedule, so the analogy costs nothing.

This is the algorithm that should suit the `cohorts` scenario, where the
conflict graph is dense and the cohort clash is the binding constraint - the
structure it is built to see.
"""

from typing import Dict, List, Set

from domains.schedule import Schedule
from domains.time_slot import TimeSlot

from algorithms.instance import Instance
from algorithms.solver import SolveResult


class GraphColouringSolver:
    name = "graph-colouring"

    def __init__(self, instance: Instance):
        self.instance = instance

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
        saturation: Dict[str, Set[TimeSlot]] = {c.id: set() for c in instance.classes}
        remaining = set(by_id)
        placed_slots: Dict[str, TimeSlot] = {}
        conflicts_pending = []

        while remaining:
            class_id = max(
                remaining,
                key=lambda cid: (
                    len(saturation[cid]),
                    len(adjacency[cid]),
                    by_id[cid].duration_hours,
                    by_id[cid].number_of_students,
                ),
            )
            remaining.discard(class_id)
            class_info = by_id[class_id]

            slot = self._place(schedule, class_info)
            if slot is None:
                conflicts_pending.append(class_info)
                continue

            placed_slots[class_id] = slot
            for neighbour in adjacency[class_id]:
                if neighbour in remaining:
                    saturation[neighbour].add(slot)

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

        for time_slot in self.instance.candidate_slots(class_info):
            for room in self.instance.candidate_rooms(class_info):
                if schedule.validate(class_info, room, professor, time_slot, groups):
                    continue
                schedule.add_assignment(class_info, room, professor, time_slot, groups)
                return time_slot
        return None
