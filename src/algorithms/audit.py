"""Checks a finished schedule against the four goals, independently of the solvers."""

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Sequence, Tuple

from data.assignment import ClassAssignment
from domains.constraints import OVERSIZE_FACTOR

from algorithms.instance import Instance


@dataclass
class Audit:
    """Every violation of goals 1-4 found in a schedule.

    Clash entries are (who, class id, class id) tuples, where `who` is the
    group, professor or room involved.
    """

    # Goal 1 - people
    student_clashes: List[Tuple[str, str, str]] = field(default_factory=list)  # (group, class, class)
    professor_clashes: List[Tuple[str, str, str]] = field(default_factory=list)  # (professor, class, class)
    students_double_booked: int = 0
    # Goal 2 - rooms
    room_double_bookings: List[Tuple[str, str, str]] = field(default_factory=list)  # (room, class, class)
    # Goal 3 - capacity
    over_capacity: List[ClassAssignment] = field(default_factory=list)
    # Goal 4 - waste (soft)
    oversized: List[ClassAssignment] = field(default_factory=list)
    wasted_seats: int = 0

    @property
    def hard_violations(self) -> int:
        """Number of violations of goals 1-3."""
        return (
            len(self.student_clashes)
            + len(self.professor_clashes)
            + len(self.room_double_bookings)
            + len(self.over_capacity)
        )

    @property
    def is_valid(self) -> bool:
        """True when goals 1-3 all hold."""
        return self.hard_violations == 0

    def summary(self) -> str:
        """One line with the verdict and a count for each goal."""
        verdict = "VALID" if self.is_valid else f"INVALID ({self.hard_violations} hard violations)"
        return (
            f"{verdict}: "
            f"1 people clashes={len(self.student_clashes) + len(self.professor_clashes)} "
            f"({self.students_double_booked} students double-booked), "
            f"2 room double-bookings={len(self.room_double_bookings)}, "
            f"3 over capacity={len(self.over_capacity)}, "
            f"4 oversized rooms={len(self.oversized)} (wasted seats {self.wasted_seats})"
        )


def audit(assignments: Sequence[ClassAssignment], instance: Instance) -> Audit:
    """Check every pair of placements and every room against goals 1-4.

    Args:
        assignments: the placements of a finished schedule.
        instance: the problem, used to look up each class's student groups.

    Returns:
        An `Audit` listing each violation found.
    """
    result = Audit()

    groups_by_class: Dict[str, List] = {c.id: instance.groups_for(c) for c in instance.classes}
    double_booked_groups = {}

    for a, b in combinations(assignments, 2):
        if not a.time_slot.overlaps(b.time_slot):
            continue
        pair = (a.class_info.id, b.class_info.id)
        if a.room.id == b.room.id:
            result.room_double_bookings.append((a.room.id, *pair))
        if a.professor.id == b.professor.id:
            result.professor_clashes.append((a.professor.id, *pair))
        groups_of_b = {g.id for g in groups_by_class.get(pair[1], ())}
        for group in groups_by_class.get(pair[0], ()):
            if group.id in groups_of_b:
                result.student_clashes.append((group.id, *pair))
                double_booked_groups[group.id] = group

    result.students_double_booked = sum(g.size for g in double_booked_groups.values())

    for assignment in assignments:
        students = assignment.class_info.number_of_students
        capacity = assignment.room.capacity
        if students > capacity:
            result.over_capacity.append(assignment)
        if capacity > OVERSIZE_FACTOR * max(students, 1):
            result.oversized.append(assignment)
        result.wasted_seats += max(capacity - students, 0)

    return result
