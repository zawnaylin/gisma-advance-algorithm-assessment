"""One problem instance, with the lookups and analysis every solver needs.

The four algorithms differ in how they search, not in what they are searching.
Room candidates, legal time windows, why a class failed and which capacity tier
is oversubscribed are all the same questions whoever is asking, so they live
here once and each solver composes an Instance rather than inheriting from it.
"""

from collections import Counter
from typing import Dict, List, Sequence, Tuple

from algorithms.solver import (
    GROUP_CONTENTION,
    NO_ROOM_LARGE_ENOUGH,
    PROFESSOR_CONTENTION,
    PROFESSOR_OVERLOADED,
    ROOM_CONTENTION,
    CapacityDeficit,
    Conflict,
)
from domains.constraints import AVAILABLE_DAY, END_TIME, START_TIME
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.schedule import Schedule
from domains.student_group import StudentGroup
from domains.time_slot import TimeSlot

TEACHABLE_HOURS_PER_WEEK = len(AVAILABLE_DAY) * (END_TIME - START_TIME)


class Instance:
    def __init__(
        self,
        classes: Sequence[ClassInformation],
        rooms: Sequence[Room],
        professors: Sequence[Professor],
        groups: Sequence[StudentGroup] = (),
        name: str = "instance",
    ):
        self.name = name
        self.classes = list(classes)
        self.rooms = list(rooms)
        self.professors = list(professors)
        self.groups = list(groups)

        self._professors_by_id: Dict[str, Professor] = {p.id: p for p in self.professors}
        self._groups_by_class_id: Dict[str, List[StudentGroup]] = {}
        for group in self.groups:
            for class_info in group.classes:
                self._groups_by_class_id.setdefault(class_info.id, []).append(group)

        self._rooms_by_size: Dict[int, List[Room]] = {}
        self._peers_by_class_id: Dict[str, frozenset] = {}
        self._slots_by_duration: Dict[int, List[TimeSlot]] = {}

        self._professor_hours: Counter = Counter()
        for class_info in self.classes:
            self._professor_hours[class_info.professor_id] += class_info.duration_hours

    @classmethod
    def from_scenario(cls, scenario) -> "Instance":
        return cls(
            scenario.classes, scenario.rooms, scenario.professors, scenario.groups, scenario.name
        )

    def __repr__(self) -> str:
        return (
            f"Instance(name={self.name!r}, classes={len(self.classes)}, "
            f"rooms={len(self.rooms)}, groups={len(self.groups)})"
        )

    # --- lookups ----------------------------------------------------------

    def professor_for(self, class_info: ClassInformation) -> Professor:
        professor = self._professors_by_id.get(class_info.professor_id)
        if professor is None:
            raise ValueError(
                f"Class {class_info.id} refers to unknown professor {class_info.professor_id}."
            )
        return professor

    def groups_for(self, class_info: ClassInformation) -> List[StudentGroup]:
        return self._groups_by_class_id.get(class_info.id, [])

    def candidate_rooms(self, class_info: ClassInformation) -> List[Room]:
        """Best fit: the smallest room that still holds the class, so the large
        rooms stay free for the classes that have no alternative. Cached per
        class size, since only the head count decides the answer.
        """
        size = class_info.number_of_students
        if size not in self._rooms_by_size:
            self._rooms_by_size[size] = sorted(
                (room for room in self.rooms if room.has_capacity(size)),
                key=lambda room: room.capacity,
            )
        return self._rooms_by_size[size]

    def candidate_slots(self, class_info: ClassInformation) -> List[TimeSlot]:
        """Every legal window for a class of this length, in chronological
        order. A longer class has fewer of them.
        """
        duration = class_info.duration_hours
        if duration not in self._slots_by_duration:
            slots = []
            for day in AVAILABLE_DAY:
                for start_hour in range(START_TIME, END_TIME - duration + 1):
                    slots.append(TimeSlot(day, start_hour, start_hour + duration))
            self._slots_by_duration[duration] = slots
        return self._slots_by_duration[duration]

    def placements(self, class_info: ClassInformation) -> List[Tuple[TimeSlot, Room]]:
        return [(slot, room) for slot in self.candidate_slots(class_info)
                for room in self.candidate_rooms(class_info)]

    # --- ordering ---------------------------------------------------------

    def most_constrained_first(self) -> List[ClassInformation]:
        """A long class has the fewest legal start hours, a big one fits in the
        fewest rooms, and a class shared by many cohorts collides with the most
        timetables. Placing those first leaves the flexible ones to absorb what
        is left.
        """
        return sorted(
            self.classes,
            key=lambda c: (c.duration_hours, c.number_of_students, len(self.groups_for(c))),
            reverse=True,
        )

    def is_placeable(self, class_info: ClassInformation) -> bool:
        """False only when no room in the estate could ever hold this class.

        Professor overload deliberately does not count here. A professor booked
        for 60h still teaches 40 of them, so the classes are placed until the
        week runs out and only the excess is reported - skipping all of them
        would lose placements a greedy pass would have made.
        """
        return bool(self.candidate_rooms(class_info))

    def peers(self, class_info: ClassInformation) -> frozenset:
        """Ids of the classes sharing at least one cohort with this one, and so
        unable to run at the same time as it."""
        if class_info.id not in self._peers_by_class_id:
            peers = set()
            for group in self.groups_for(class_info):
                peers.update(c.id for c in group.classes)
            peers.discard(class_info.id)
            self._peers_by_class_id[class_info.id] = frozenset(peers)
        return self._peers_by_class_id[class_info.id]

    # --- analysis ---------------------------------------------------------

    def capacity_deficits(self) -> List[CapacityDeficit]:
        """Room-hours promised against room-hours owned, at every capacity tier.

        Classes that fit nowhere are left out; they are already reported one by
        one as NO_ROOM_LARGE_ENOUGH.
        """
        capacities = sorted({room.capacity for room in self.rooms})
        smallest_fit = {}
        for class_info in self.classes:
            fits = [c for c in capacities if c >= class_info.number_of_students]
            if fits:
                smallest_fit[class_info.id] = fits[0]

        deficits = []
        for tier in capacities:
            rooms = sum(1 for room in self.rooms if room.capacity >= tier)
            supply = rooms * TEACHABLE_HOURS_PER_WEEK
            demand = sum(
                c.duration_hours
                for c in self.classes
                if smallest_fit.get(c.id) is not None and smallest_fit[c.id] >= tier
            )
            if demand > supply:
                deficits.append(CapacityDeficit(tier, rooms, supply, demand))
        return deficits

    def diagnose(self, schedule: Schedule, class_info: ClassInformation) -> Conflict:
        """Name the reason this class found no home.

        Structural causes are checked first because they hold regardless of what
        the search did; only then is the blocked-window tally worth reading.
        """
        fitting_rooms = self.candidate_rooms(class_info)
        if not fitting_rooms:
            largest = max((room.capacity for room in self.rooms), default=0)
            return Conflict(
                class_info,
                NO_ROOM_LARGE_ENOUGH,
                f"needs {class_info.number_of_students} seats, largest room holds {largest}.",
            )

        booked = self._professor_hours[class_info.professor_id]
        if booked > TEACHABLE_HOURS_PER_WEEK:
            return Conflict(
                class_info,
                PROFESSOR_OVERLOADED,
                f"professor {class_info.professor_id} is down for {booked}h of teaching, "
                f"but the week only holds {TEACHABLE_HOURS_PER_WEEK}h.",
            )

        professor = self.professor_for(class_info)
        groups = self.groups_for(class_info)
        slots = self.candidate_slots(class_info)

        blockers: Counter = Counter()
        for time_slot in slots:
            if not schedule.check_professor_available(professor, time_slot):
                blockers[PROFESSOR_CONTENTION] += 1
            elif any(not schedule.check_group_available(g, time_slot) for g in groups):
                blockers[GROUP_CONTENTION] += 1
            else:
                blockers[ROOM_CONTENTION] += 1

        cause, count = blockers.most_common(1)[0]
        if len(fitting_rooms) == 1:
            rooms_booked = "the only room that fits was booked"
        else:
            rooms_booked = f"all {len(fitting_rooms)} rooms that fit were booked"
        explanation = {
            PROFESSOR_CONTENTION: f"professor {class_info.professor_id} was already teaching",
            GROUP_CONTENTION: "a student group already had a class",
            ROOM_CONTENTION: rooms_booked,
        }[cause]
        return Conflict(
            class_info, cause, f"{explanation} in {count} of {len(slots)} candidate windows."
        )
