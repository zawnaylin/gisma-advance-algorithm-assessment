"""Shared result types and the protocol every solver implements."""

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, runtime_checkable

from data.assignment import ClassAssignment
from domains.class_information import ClassInformation
from domains.schedule import Schedule

NO_ROOM_LARGE_ENOUGH = "no_room_large_enough"
PROFESSOR_OVERLOADED = "professor_overloaded"
ROOM_CONTENTION = "room_contention"
PROFESSOR_CONTENTION = "professor_contention"
GROUP_CONTENTION = "group_contention"
SEARCH_EXHAUSTED = "search_exhausted"

# Causes no search can fix.
STRUCTURAL_CAUSES = frozenset({NO_ROOM_LARGE_ENOUGH, PROFESSOR_OVERLOADED})

# Suggested manual action for each cause.
MANUAL_ACTIONS = {
    NO_ROOM_LARGE_ENOUGH: "split the class into sections or book a larger venue",
    PROFESSOR_OVERLOADED: "reassign some of these classes to another professor",
    ROOM_CONTENTION: "add room-hours (extra room or evening slot) or move a class by hand",
    PROFESSOR_CONTENTION: "move one of the professor's classes by hand",
    GROUP_CONTENTION: "split the cohort or drop an elective from its timetable",
    SEARCH_EXHAUSTED: "rerun with a larger search budget or place by hand",
}


@dataclass(frozen=True)
class CapacityDeficit:
    """Teaching hours that need rooms of at least `capacity` seats, against
    the hours those rooms offer in a week."""

    capacity: int
    rooms: int
    supply_hours: int
    demand_hours: int

    @property
    def shortfall_hours(self) -> int:
        """Hours that cannot be placed in any schedule."""
        return self.demand_hours - self.supply_hours

    def __str__(self) -> str:
        return (
            f"classes needing {self.capacity}+ seats want {self.demand_hours}h, but the "
            f"{self.rooms} room(s) that large only offer {self.supply_hours}h "
            f"- at least {self.shortfall_hours}h cannot be placed."
        )


@dataclass(frozen=True)
class Conflict:
    """A class that could not be placed, and why."""

    class_info: ClassInformation
    cause: str
    detail: str

    @property
    def is_structural(self) -> bool:
        """True when no search could place this class."""
        return self.cause in STRUCTURAL_CAUSES

    def __str__(self) -> str:
        c = self.class_info
        return f"{c.id} {c.name!r} ({c.number_of_students} students, {c.duration_hours}h): {self.detail}"


@dataclass
class SolveResult:
    """The output of a solver: placements, conflicts and solver statistics."""

    solver: str
    schedule: Schedule
    assignments: List[ClassAssignment] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    capacity_deficits: List[CapacityDeficit] = field(default_factory=list)
    stats: Dict[str, object] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """True when every class was placed."""
        return not self.conflicts

    @property
    def coverage(self) -> float:
        """Share of the classes placed, from 0.0 to 1.0."""
        total = len(self.assignments) + len(self.conflicts)
        return len(self.assignments) / total if total else 1.0

    @property
    def scheduled_hours(self) -> int:
        """Teaching hours placed."""
        return sum(a.class_info.duration_hours for a in self.assignments)

    @property
    def wasted_seats(self) -> int:
        """Empty seats summed over every placement."""
        return sum(a.room.capacity - a.class_info.number_of_students for a in self.assignments)

    @property
    def flagged_for_manual_intervention(self) -> List[Conflict]:
        """Classes that need a person to place them."""
        return list(self.conflicts)

    @property
    def structural_conflicts(self) -> List[Conflict]:
        """Conflicts no search could fix."""
        return [c for c in self.conflicts if c.is_structural]

    @property
    def contention_conflicts(self) -> List[Conflict]:
        """Conflicts a better search might fix."""
        return [c for c in self.conflicts if not c.is_structural]

    def conflicts_by_cause(self) -> Dict[str, List[Conflict]]:
        """Conflicts grouped by cause, the most common cause first."""
        grouped: Dict[str, List[Conflict]] = {}
        for conflict in self.conflicts:
            grouped.setdefault(conflict.cause, []).append(conflict)
        return dict(sorted(grouped.items(), key=lambda kv: -len(kv[1])))

    def report(self, title: str | None = None, examples: int = 3) -> str:
        """Render a readable summary of the result.

        Args:
            title: heading for the first line; defaults to the solver name.
            examples: how many conflicts to list for each cause.

        Returns:
            The report as multi-line text.
        """
        total = len(self.assignments) + len(self.conflicts)
        lines = [
            f"{title or self.solver}: placed {len(self.assignments)} of {total} classes "
            f"({self.coverage:.1%}), {self.scheduled_hours} teaching hours scheduled"
        ]

        if self.stats:
            lines.append("  " + ", ".join(f"{k}={v}" for k, v in self.stats.items()))

        for deficit in self.capacity_deficits:
            lines.append(f"  STRUCTURAL capacity shortfall: {deficit}")

        if not self.conflicts:
            lines.append("  no conflicts")
            return "\n".join(lines)

        lines.append(
            f"  {len(self.structural_conflicts)} structural, "
            f"{len(self.contention_conflicts)} contention"
        )
        for cause, conflicts in self.conflicts_by_cause().items():
            if conflicts[0].is_structural:
                kind = "STRUCTURAL - unplaceable in this instance"
            else:
                kind = "CONTENTION - a better search may recover these"
            lines.append(f"  {cause} ({len(conflicts)}) - {kind}")
            for conflict in conflicts[:examples]:
                lines.append(f"      {conflict}")
            if len(conflicts) > examples:
                lines.append(f"      ... and {len(conflicts) - examples} more")
        return "\n".join(lines)

    def manual_intervention_report(self) -> str:
        """Render the unplaced classes grouped by cause, with a suggested action
        for each cause."""
        flagged = self.flagged_for_manual_intervention
        if not flagged:
            return "  nothing flagged for manual intervention"

        lines = [f"  FLAGGED FOR MANUAL INTERVENTION: {len(flagged)} class(es)"]
        for cause, conflicts in self.conflicts_by_cause().items():
            lines.append(f"    {cause} -> {MANUAL_ACTIONS.get(cause, 'review by hand')}")
            lines.append("      " + ", ".join(c.class_info.id for c in conflicts))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SolveResult(solver={self.solver!r}, assigned={len(self.assignments)}, "
            f"conflicts={len(self.conflicts)}, coverage={self.coverage:.1%})"
        )


@runtime_checkable
class Solver(Protocol):
    """Anything with a `name` and a `solve()` that returns a `SolveResult`."""

    name: str

    def solve(self) -> SolveResult:
        """Build a schedule for the solver's instance."""
        ...
