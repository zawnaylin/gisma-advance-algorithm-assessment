"""The contract every algorithm in this package satisfies.

`Solver` is a Protocol rather than a base class: nothing inherits from it, and
a class satisfies it by having the right shape. That keeps the four algorithms
independent of each other while still letting a caller treat them alike:

    for solver in (GreedySolver(instance), BacktrackingSolver(instance), ...):
        print(solver.solve().report())

`SolveResult` is the opposite - a concrete class, shared by all of them,
because what they produce really is the same thing. `stats` is the one place
an algorithm reports numbers only it has, such as how many times it retreated.
"""

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

# Causes the instance itself guarantees - a different search cannot help.
STRUCTURAL_CAUSES = frozenset({NO_ROOM_LARGE_ENOUGH, PROFESSOR_OVERLOADED})

# What a timetabler would do about each cause once the search has given up.
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
    """More teaching hours need a room of this size than the estate can supply.

    A per-class check cannot see this: every one of these classes has a room
    that fits, they just cannot all have one at once. The shortfall is a lower
    bound on the hours no search will ever place.
    """

    capacity: int
    rooms: int
    supply_hours: int
    demand_hours: int

    @property
    def shortfall_hours(self) -> int:
        return self.demand_hours - self.supply_hours

    def __str__(self) -> str:
        return (
            f"classes needing {self.capacity}+ seats want {self.demand_hours}h, but the "
            f"{self.rooms} room(s) that large only offer {self.supply_hours}h "
            f"- at least {self.shortfall_hours}h cannot be placed."
        )


@dataclass(frozen=True)
class Conflict:
    class_info: ClassInformation
    cause: str
    detail: str

    @property
    def is_structural(self) -> bool:
        return self.cause in STRUCTURAL_CAUSES

    def __str__(self) -> str:
        c = self.class_info
        return f"{c.id} {c.name!r} ({c.number_of_students} students, {c.duration_hours}h): {self.detail}"


@dataclass
class SolveResult:
    solver: str
    schedule: Schedule
    assignments: List[ClassAssignment] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    capacity_deficits: List[CapacityDeficit] = field(default_factory=list)
    stats: Dict[str, object] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return not self.conflicts

    @property
    def coverage(self) -> float:
        total = len(self.assignments) + len(self.conflicts)
        return len(self.assignments) / total if total else 1.0

    @property
    def scheduled_hours(self) -> int:
        return sum(a.class_info.duration_hours for a in self.assignments)

    @property
    def wasted_seats(self) -> int:
        """Empty seats summed over every placement - what Stage 3 minimises."""
        return sum(a.room.capacity - a.class_info.number_of_students for a in self.assignments)

    @property
    def flagged_for_manual_intervention(self) -> List[Conflict]:
        """Every class the search could not place. Nothing is dropped silently:
        each one comes back with the reason, for a person to resolve."""
        return list(self.conflicts)

    @property
    def structural_conflicts(self) -> List[Conflict]:
        return [c for c in self.conflicts if c.is_structural]

    @property
    def contention_conflicts(self) -> List[Conflict]:
        return [c for c in self.conflicts if not c.is_structural]

    def conflicts_by_cause(self) -> Dict[str, List[Conflict]]:
        grouped: Dict[str, List[Conflict]] = {}
        for conflict in self.conflicts:
            grouped.setdefault(conflict.cause, []).append(conflict)
        return dict(sorted(grouped.items(), key=lambda kv: -len(kv[1])))

    def report(self, title: str | None = None, examples: int = 3) -> str:
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
        """The hand-off list: which classes a person has to deal with, and what
        kind of action each group needs."""
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
    """Anything that turns an instance into a schedule.

    A class satisfies this by having `name` and `solve()` - there is nothing to
    inherit and nothing to register.
    """

    name: str

    def solve(self) -> SolveResult:
        ...
