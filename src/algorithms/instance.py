"""A problem instance with the lookups and failure analysis every solver shares."""

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
from domains.constraints import AVAILABLE_DAY, END_TIME, OVERSIZE_FACTOR, START_TIME
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.schedule import Schedule
from domains.student_group import StudentGroup
from domains.time_slot import TimeSlot

TEACHABLE_HOURS_PER_WEEK = len(AVAILABLE_DAY) * (END_TIME - START_TIME)


def is_oversized(class_info: ClassInformation, room: Room) -> bool:
    """True when the room has more than OVERSIZE_FACTOR seats per student (goal 4)."""
    return room.capacity > OVERSIZE_FACTOR * max(class_info.number_of_students, 1)


class Instance:
    """The classes, rooms, professors and student groups of one timetabling problem."""

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
        self._placements: Dict[Tuple[int, int, bool], List[Tuple[TimeSlot, Room]]] = {}

        self._professor_hours: Counter = Counter()
        for class_info in self.classes:
            self._professor_hours[class_info.professor_id] += class_info.duration_hours

    @classmethod
    def from_scenario(cls, scenario) -> "Instance":
        """Build an instance from a loaded `Scenario`."""
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
        """The professor who teaches the class.

        Raises:
            ValueError: if the class names a professor the instance does not have.
        """
        professor = self._professors_by_id.get(class_info.professor_id)
        if professor is None:
            raise ValueError(
                f"Class {class_info.id} refers to unknown professor {class_info.professor_id}."
            )
        return professor

    def groups_for(self, class_info: ClassInformation) -> List[StudentGroup]:
        """The student groups that attend the class."""
        return self._groups_by_class_id.get(class_info.id, [])

    def candidate_rooms(self, class_info: ClassInformation) -> List[Room]:
        """Rooms large enough for the class, smallest first."""
        size = class_info.number_of_students
        if size not in self._rooms_by_size:
            self._rooms_by_size[size] = sorted(
                (room for room in self.rooms if room.has_capacity(size)),
                key=lambda room: room.capacity,
            )
        return self._rooms_by_size[size]

    def candidate_slots(self, class_info: ClassInformation) -> List[TimeSlot]:
        """Every legal time slot for the class's duration, in chronological order."""
        duration = class_info.duration_hours
        if duration not in self._slots_by_duration:
            slots = []
            for day in AVAILABLE_DAY:
                for start_hour in range(START_TIME, END_TIME - duration + 1):
                    slots.append(TimeSlot(day, start_hour, start_hour + duration))
            self._slots_by_duration[duration] = slots
        return self._slots_by_duration[duration]

    def placements(
        self, class_info: ClassInformation, avoid_oversized: bool = False
    ) -> List[Tuple[TimeSlot, Room]]:
        """Every (time slot, room) pair the class may take, in the order to try them.

        Args:
            class_info: the class to place.
            avoid_oversized: if True, list all right-sized rooms at every time
                before any oversized room; otherwise order by time, then room size.

        Returns:
            The candidate pairs, in trial order.
        """
        key = (class_info.number_of_students, class_info.duration_hours, avoid_oversized)
        if key not in self._placements:
            slots = self.candidate_slots(class_info)
            rooms = self.candidate_rooms(class_info)
            if avoid_oversized:
                right_sized = [r for r in rooms if not is_oversized(class_info, r)]
                oversized = [r for r in rooms if is_oversized(class_info, r)]
                tiers = [right_sized, oversized]
            else:
                tiers = [rooms]
            self._placements[key] = [(s, r) for tier in tiers for s in slots for r in tier]
        return self._placements[key]

    # --- ordering ---------------------------------------------------------

    def most_constrained_first(self) -> List[ClassInformation]:
        """Classes sorted by duration, then head count, then number of groups,
        all descending."""
        return sorted(
            self.classes,
            key=lambda c: (c.duration_hours, c.number_of_students, len(self.groups_for(c))),
            reverse=True,
        )

    def is_placeable(self, class_info: ClassInformation) -> bool:
        """True when at least one room is large enough for the class."""
        return bool(self.candidate_rooms(class_info))

    def peers(self, class_info: ClassInformation) -> frozenset:
        """Ids of the classes that share at least one student group with this one."""
        if class_info.id not in self._peers_by_class_id:
            peers = set()
            for group in self.groups_for(class_info):
                peers.update(c.id for c in group.classes)
            peers.discard(class_info.id)
            self._peers_by_class_id[class_info.id] = frozenset(peers)
        return self._peers_by_class_id[class_info.id]

    # --- analysis ---------------------------------------------------------

    def capacity_deficits(self) -> List[CapacityDeficit]:
        """Capacity tiers whose classes need more hours than their rooms offer.

        Classes that fit in no room are excluded.
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
        """Explain why the class could not be placed in the schedule.

        Args:
            schedule: the schedule the class failed to fit into.
            class_info: the unplaced class.

        Returns:
            A `Conflict` with the most likely cause and a readable detail.
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
