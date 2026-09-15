"""Backtracking search with ejection.

The greedy solver takes the first window that fits and never looks back. This
one starts from that schedule and then retreats: for each class greedy could
not place, it finds the placements that would work if a few committed classes
moved, ejects them, and tries to re-home them somewhere else. If they all find
a home the swap is kept; if any cannot, every change is rolled back and the
next candidate is tried.

Chronological backtracking was the obvious first attempt and it does not work
here. A depth-first search undoes its most recent decision, but the decision
that stranded a class was made near the root, hundreds of placements earlier -
300,000 steps of it recovered nothing on any scenario. Directing the retreat at
the classes that actually failed is what makes the retreat pay.

`Schedule.unassign` is what makes this affordable: a retreat touches one object,
so an attempt can be unwound exactly rather than by rebuilding the timetable.
"""

from typing import List, Optional, Set

from data.assignment import ClassAssignment
from domains.class_information import ClassInformation
from domains.schedule import Schedule

from algorithms.instance import Instance
from algorithms.solver import SEARCH_EXHAUSTED, Conflict, SolveResult

DEFAULT_STEP_BUDGET = 200_000
DEFAULT_MAX_EJECTIONS = 2
DEFAULT_DEPTH = 3


class _Transaction:
    """Records every change so a failed attempt can be undone exactly.

    Replaying the log backwards restores the schedule: an add is undone by
    unassigning, a removal by putting the original assignment back.
    """

    def __init__(self, schedule: Schedule, instance: Instance):
        self._schedule = schedule
        self._instance = instance
        self._log: List[tuple] = []

    def place(self, class_info, room, professor, time_slot) -> ClassAssignment:
        groups = self._instance.groups_for(class_info)
        assignment = self._schedule.add_assignment(class_info, room, professor, time_slot, groups)
        self._log.append(("added", class_info.id))
        return assignment

    def remove(self, class_id: str) -> Optional[ClassAssignment]:
        assignment = self._schedule.unassign(class_id)
        if assignment is not None:
            self._log.append(("removed", assignment))
        return assignment

    def savepoint(self) -> int:
        return len(self._log)

    def commit(self) -> None:
        self._log.clear()

    def rollback(self, mark: int = 0) -> None:
        while len(self._log) > mark:
            action, payload = self._log.pop()
            if action == "added":
                self._schedule.unassign(payload)
            else:
                self._schedule.add_assignment(
                    payload.class_info,
                    payload.room,
                    payload.professor,
                    payload.time_slot,
                    self._instance.groups_for(payload.class_info),
                )


class BacktrackingSolver:
    name = "backtracking"

    def __init__(
        self,
        instance: Instance,
        step_budget: int = DEFAULT_STEP_BUDGET,
        max_ejections: int = DEFAULT_MAX_EJECTIONS,
        depth: int = DEFAULT_DEPTH,
    ):
        self.instance = instance
        self.step_budget = step_budget
        self.max_ejections = max_ejections
        self.depth = depth
        self._steps = 0

    def solve(self) -> SolveResult:
        instance = self.instance
        schedule = Schedule()
        self._steps = 0

        ruled_out = []
        unplaced = []

        # First dive: the greedy schedule, which the search then improves on.
        for class_info in instance.most_constrained_first():
            if not instance.is_placeable(class_info):
                ruled_out.append(class_info)
                continue
            if not self._place_directly(schedule, class_info):
                unplaced.append(class_info)

        recovered = []
        for class_info in list(unplaced):
            if self._steps >= self.step_budget:
                break
            if self._place_by_ejection(schedule, class_info, self.depth):
                unplaced.remove(class_info)
                recovered.append(class_info.id)

        result = SolveResult(
            solver=self.name,
            schedule=schedule,
            assignments=schedule.assignments,
            capacity_deficits=instance.capacity_deficits(),
            stats={
                "steps": self._steps,
                "recovered_by_ejection": len(recovered),
                "budget_exhausted": self._steps >= self.step_budget,
            },
        )
        for class_info in ruled_out:
            result.conflicts.append(instance.diagnose(schedule, class_info))
        for class_info in unplaced:
            result.conflicts.append(self._unrecovered(schedule, class_info))
        return result

    # --- placement --------------------------------------------------------

    def _place_directly(self, schedule: Schedule, class_info: ClassInformation) -> bool:
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        for time_slot in self.instance.candidate_slots(class_info):
            for room in self.instance.candidate_rooms(class_info):
                self._steps += 1
                if schedule.validate(class_info, room, professor, time_slot, groups):
                    continue
                schedule.add_assignment(class_info, room, professor, time_slot, groups)
                return True
        return False

    def _place_by_ejection(self, schedule: Schedule, class_info: ClassInformation, depth: int) -> bool:
        transaction = _Transaction(schedule, self.instance)
        if self._attempt(schedule, class_info, depth, transaction):
            transaction.commit()
            return True
        transaction.rollback(0)
        return False

    def _attempt(
        self,
        schedule: Schedule,
        class_info: ClassInformation,
        depth: int,
        transaction: _Transaction,
    ) -> bool:
        professor = self.instance.professor_for(class_info)
        groups = self.instance.groups_for(class_info)

        # Somewhere free is always better than displacing somebody.
        for time_slot in self.instance.candidate_slots(class_info):
            for room in self.instance.candidate_rooms(class_info):
                self._steps += 1
                if not schedule.validate(class_info, room, professor, time_slot, groups):
                    transaction.place(class_info, room, professor, time_slot)
                    return True

        if depth <= 0:
            return False

        for time_slot in self.instance.candidate_slots(class_info):
            for room in self.instance.candidate_rooms(class_info):
                if self._steps >= self.step_budget:
                    return False
                self._steps += 1

                blockers = self._blockers(schedule, class_info, room, time_slot)
                if blockers is None or len(blockers) > self.max_ejections:
                    continue

                mark = transaction.savepoint()
                ejected = [transaction.remove(class_id) for class_id in blockers]
                transaction.place(class_info, room, professor, time_slot)

                if all(
                    self._attempt(schedule, a.class_info, depth - 1, transaction)
                    for a in ejected
                    if a is not None
                ):
                    return True
                transaction.rollback(mark)
        return False

    def _blockers(
        self, schedule: Schedule, class_info: ClassInformation, room, time_slot
    ) -> Optional[Set[str]]:
        """Which scheduled classes stand between this class and this placement.

        None means the placement is impossible however much is moved - the room
        is simply too small.
        """
        if not class_info.fits_in(room):
            return None

        peers = self.instance.peers(class_info)
        blockers: Set[str] = set()
        for assignment in schedule.assignments:
            if not assignment.time_slot.overlaps(time_slot):
                continue
            if (
                assignment.room.id == room.id
                or assignment.professor.id == class_info.professor_id
                or assignment.class_info.id in peers
            ):
                blockers.add(assignment.class_info.id)
        return blockers

    def _unrecovered(self, schedule: Schedule, class_info: ClassInformation) -> Conflict:
        diagnosed = self.instance.diagnose(schedule, class_info)
        # A structural cause is the better answer even when the budget also ran
        # out: the search stopping is not why this class has nowhere to go.
        if not diagnosed.is_structural and self._steps >= self.step_budget:
            return Conflict(
                class_info,
                SEARCH_EXHAUSTED,
                f"search budget of {self.step_budget} steps ran out; {diagnosed.detail}",
            )
        return diagnosed
