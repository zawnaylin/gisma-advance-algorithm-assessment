"""Local-search improvement.

The other three answer "can everything be placed?". Once the answer is yes, the
timetable can still be bad: a seminar of twelve sitting in a 500-seat hall, or a
cohort with a free hour every morning between two classes. This one starts from
a finished schedule and moves classes one at a time, keeping only the moves that
lower a cost.

It is a hill climber: first improvement wins, and it stops when a full pass
finds nothing better. That reaches a local optimum, not the best timetable
there is - the honest claim is that it never makes one worse.

Because it takes a schedule and returns a schedule, it is the odd one out of the
four. `solve()` runs a seed solver first so it satisfies the same protocol, and
`improve()` is there for when the starting schedule already exists.
"""

from dataclasses import dataclass
from typing import Dict, List

from domains.schedule import Schedule
from domains.student_group import StudentGroup

from algorithms.backtracker import BacktrackingSolver
from algorithms.instance import Instance
from algorithms.solver import SolveResult

UNPLACED_PENALTY = 1000
GAP_PENALTY = 3
DEFAULT_STEP_BUDGET = 200_000
DEFAULT_MAX_PASSES = 8


@dataclass(frozen=True)
class Cost:
    """Lower is better. Coverage dominates: no amount of tidying is worth
    dropping a class."""

    unplaced: int
    wasted_seats: int
    gap_hours: int

    @property
    def total(self) -> int:
        return UNPLACED_PENALTY * self.unplaced + self.wasted_seats + GAP_PENALTY * self.gap_hours

    def __str__(self) -> str:
        return (
            f"cost={self.total} (unplaced={self.unplaced}, "
            f"wasted_seats={self.wasted_seats}, gap_hours={self.gap_hours})"
        )


class Optimizer:
    name = "optimizer"

    def __init__(
        self,
        instance: Instance,
        seed=None,
        step_budget: int = DEFAULT_STEP_BUDGET,
        max_passes: int = DEFAULT_MAX_PASSES,
    ):
        self.instance = instance
        self.seed = seed if seed is not None else BacktrackingSolver(instance)
        self.step_budget = step_budget
        self.max_passes = max_passes

    def solve(self) -> SolveResult:
        return self.improve(self.seed.solve())

    def improve(self, result: SolveResult) -> SolveResult:
        instance = self.instance
        schedule = result.schedule
        unplaced = len(result.conflicts)

        before = self.evaluate(schedule, unplaced)
        steps = 0
        passes = 0
        moves = 0

        while passes < self.max_passes and steps < self.step_budget:
            passes += 1
            improved_this_pass = 0

            for assignment in schedule.assignments:
                if steps >= self.step_budget:
                    break
                steps += 1
                if self._relocate(schedule, assignment.class_info.id):
                    improved_this_pass += 1

            moves += improved_this_pass
            if improved_this_pass == 0:
                break

        after = self.evaluate(schedule, unplaced)
        return SolveResult(
            solver=self.name,
            schedule=schedule,
            assignments=schedule.assignments,
            conflicts=list(result.conflicts),
            capacity_deficits=list(result.capacity_deficits),
            stats={
                "seeded_by": result.solver,
                "passes": passes,
                "moves": moves,
                "cost_before": before.total,
                "cost_after": after.total,
                "wasted_seats": after.wasted_seats,
                "gap_hours": after.gap_hours,
            },
        )

    # --- cost -------------------------------------------------------------

    def evaluate(self, schedule: Schedule, unplaced: int) -> Cost:
        wasted = sum(
            a.room.capacity - a.class_info.number_of_students for a in schedule.assignments
        )
        gaps = sum(self._gap_hours(schedule, g) for g in self.instance.groups)
        return Cost(unplaced=unplaced, wasted_seats=wasted, gap_hours=gaps)

    def _gap_hours(self, schedule: Schedule, group: StudentGroup) -> int:
        """Hours a cohort waits between its first and last class each day."""
        by_day: Dict[int, List] = {}
        for class_info in group.classes:
            assignment = schedule.assignment_for(class_info.id)
            if assignment is not None:
                by_day.setdefault(assignment.time_slot.day, []).append(assignment.time_slot)

        total = 0
        for slots in by_day.values():
            slots.sort(key=lambda s: s.start_hour)
            span = slots[-1].end_hour - slots[0].start_hour
            taught = sum(s.end_hour - s.start_hour for s in slots)
            total += span - taught
        return total

    # --- moves ------------------------------------------------------------

    def _relocate(self, schedule: Schedule, class_id: str) -> bool:
        """Move one class to the best window found, or leave it where it was."""
        original = schedule.assignment_for(class_id)
        if original is None:
            return False

        instance = self.instance
        class_info = original.class_info
        professor = original.professor
        groups = instance.groups_for(class_info)

        baseline = self._local_cost(schedule, class_info, original.room)
        schedule.unassign(class_id)

        best = None
        best_cost = baseline
        for time_slot in instance.candidate_slots(class_info):
            for room in instance.candidate_rooms(class_info):
                if schedule.validate(class_info, room, professor, time_slot, groups):
                    continue
                schedule.add_assignment(class_info, room, professor, time_slot, groups)
                cost = self._local_cost(schedule, class_info, room)
                schedule.unassign(class_id)
                if cost < best_cost:
                    best_cost = cost
                    best = (room, time_slot)

        room, time_slot = best if best is not None else (original.room, original.time_slot)
        schedule.add_assignment(class_info, room, professor, time_slot, groups)
        return best is not None

    def _local_cost(self, schedule: Schedule, class_info, room) -> int:
        """Only the parts of the cost this class can change: the seats it
        wastes, and the gaps in the cohorts it belongs to."""
        wasted = room.capacity - class_info.number_of_students
        gaps = sum(
            self._gap_hours(schedule, group) for group in self.instance.groups_for(class_info)
        )
        return wasted + GAP_PENALTY * gaps
