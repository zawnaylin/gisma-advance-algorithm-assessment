"""Stage 1: the greedy baseline."""

from domains.schedule import Schedule

from algorithms.instance import Instance
from algorithms.solver import SolveResult


class GreedySolver:
    """Places each class, hardest first, in the first free (time slot, room) pair."""

    name = "greedy"

    def __init__(self, instance: Instance):
        self.instance = instance

    def solve(self) -> SolveResult:
        """Place every class once; unplaced classes are returned as conflicts."""
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
        """Book the first valid (time slot, room) pair; None if there is none."""
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        for time_slot, room in self.instance.placements(class_info):
            if schedule.validate(class_info, room, professor, time_slot, groups):
                continue
            return schedule.add_assignment(class_info, room, professor, time_slot, groups)

        return None
