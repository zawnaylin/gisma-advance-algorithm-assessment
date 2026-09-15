"""Greedy timetabling.

Walks the classes once, most constrained first, and gives each one the first
(time slot, room) pair that breaks no constraint. It never revisits a decision,
so it is fast but incomplete: a class that finds nothing left is reported as a
conflict rather than triggering a retreat.

This is the baseline the other three are measured against.
"""

from domains.schedule import Schedule

from algorithms.instance import Instance
from algorithms.solver import SolveResult


class GreedySolver:
    name = "greedy"

    def __init__(self, instance: Instance):
        self.instance = instance

    def solve(self) -> SolveResult:
        schedule = Schedule()
        result = SolveResult(
            solver=self.name,
            schedule=schedule,
            capacity_deficits=self.instance.capacity_deficits(),
        )

        for class_info in self.instance.most_constrained_first():
            assignment = self._place(schedule, class_info)
            if assignment is not None:
                result.assignments.append(assignment)
            else:
                result.conflicts.append(self.instance.diagnose(schedule, class_info))

        return result

    def _place(self, schedule: Schedule, class_info):
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        for time_slot in self.instance.candidate_slots(class_info):
            for room in self.instance.candidate_rooms(class_info):
                if schedule.validate(class_info, room, professor, time_slot, groups):
                    continue
                return schedule.add_assignment(class_info, room, professor, time_slot, groups)

        return None
