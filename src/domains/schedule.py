"""The timetable: every booking of rooms, professors and student groups."""

from typing import Dict, Iterable, List, Tuple

from data.assignment import ClassAssignment
from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup
from domains.time_slot import TimeSlot


class Schedule:
    """Placed classes, and the room and professor bookings they hold."""

    def __init__(self):
        self._assignments: List[ClassAssignment] = []
        self._assignment_by_class_id: Dict[str, ClassAssignment] = {}
        self._room_slots: Dict[str, List[TimeSlot]] = {}
        self._professor_slots: Dict[str, List[TimeSlot]] = {}

    @property
    def assignments(self) -> List[ClassAssignment]:
        """A copy of every placement, in the order they were made."""
        return list(self._assignments)

    def assignment_for(self, class_id: str) -> ClassAssignment | None:
        """The placement of a class, or None if it is not scheduled."""
        return self._assignment_by_class_id.get(class_id)

    def slots_for_room(self, room: Room) -> Tuple[TimeSlot, ...]:
        """Time slots in which the room is booked."""
        return tuple(self._room_slots.get(room.id, ()))

    def slots_for_professor(self, professor: Professor) -> Tuple[TimeSlot, ...]:
        """Time slots in which the professor is teaching."""
        return tuple(self._professor_slots.get(professor.id, ()))

    def check_capacity(self, class_info: ClassInformation, room: Room) -> bool:
        """True when the class fits in the room (goal 3)."""
        return class_info.fits_in(room)

    def check_room_available(self, room: Room, time_slot: TimeSlot) -> bool:
        """True when the room is free for the whole slot (goal 2)."""
        return self._is_free(self._room_slots, room.id, time_slot)

    def check_professor_available(self, professor: Professor, time_slot: TimeSlot) -> bool:
        """True when the professor is free for the whole slot (goal 1)."""
        return self._is_free(self._professor_slots, professor.id, time_slot)

    def check_group_available(self, group: StudentGroup, time_slot: TimeSlot) -> bool:
        """True when none of the group's classes overlaps the slot (goal 1)."""
        for class_info in group.classes:
            existing = self._assignment_by_class_id.get(class_info.id)
            if existing is not None and existing.time_slot.overlaps(time_slot):
                return False
        return True

    def validate(
        self,
        class_info: ClassInformation,
        room: Room,
        professor: Professor,
        time_slot: TimeSlot,
        groups: Iterable[StudentGroup] = (),
    ) -> List[str]:
        """Check a placement against every hard constraint.

        Args:
            class_info: the class to place.
            room: the proposed room.
            professor: the class's professor.
            time_slot: the proposed time slot.
            groups: the student groups attending the class.

        Returns:
            A message for each violated constraint; empty if the placement is valid.
        """
        violations = []

        if not self.check_capacity(class_info, room):
            violations.append(
                f"Room {room.id} (capacity {room.capacity}) cannot fit "
                f"{class_info.number_of_students} students for class {class_info.id}."
            )

        if not self.check_room_available(room, time_slot):
            violations.append(f"Room {room.id} is already booked during {time_slot}.")

        if not self.check_professor_available(professor, time_slot):
            violations.append(f"Professor {professor.id} is already teaching during {time_slot}.")

        for group in groups:
            if not self.check_group_available(group, time_slot):
                violations.append(f"Student group {group.id} has a conflicting class during {time_slot}.")

        return violations

    def add_assignment(
        self,
        class_info: ClassInformation,
        room: Room,
        professor: Professor,
        time_slot: TimeSlot,
        groups: Iterable[StudentGroup] = (),
    ) -> ClassAssignment:
        """Book a placement.

        Raises:
            ValueError: if the class is already scheduled or the placement
                breaks a hard constraint.
        """
        if class_info.id in self._assignment_by_class_id:
            raise ValueError(f"Class {class_info.id} is already scheduled; unassign it first.")

        violations = self.validate(class_info, room, professor, time_slot, groups)
        if violations:
            raise ValueError("; ".join(violations))

        self._occupy(self._room_slots, room.id, time_slot)
        self._occupy(self._professor_slots, professor.id, time_slot)

        assignment = ClassAssignment(class_info=class_info, room=room, professor=professor, time_slot=time_slot)
        self._assignments.append(assignment)
        self._assignment_by_class_id[class_info.id] = assignment
        return assignment

    def unassign(self, class_id: str) -> ClassAssignment | None:
        """Remove a placement and free its bookings.

        Returns:
            The removed assignment, or None if the class was not scheduled.
        """
        assignment = self._assignment_by_class_id.pop(class_id, None)
        if assignment is None:
            return None

        self._assignments.remove(assignment)
        self._release(self._room_slots, assignment.room.id, assignment.time_slot)
        self._release(self._professor_slots, assignment.professor.id, assignment.time_slot)
        return assignment

    @staticmethod
    def _is_free(slots_by_id: Dict[str, List[TimeSlot]], key: str, time_slot: TimeSlot) -> bool:
        """True when no booking under `key` overlaps the slot."""
        return not any(time_slot.overlaps(s) for s in slots_by_id.get(key, ()))

    @staticmethod
    def _occupy(slots_by_id: Dict[str, List[TimeSlot]], key: str, time_slot: TimeSlot) -> None:
        """Record a booking under `key`."""
        slots_by_id.setdefault(key, []).append(time_slot)

    @staticmethod
    def _release(slots_by_id: Dict[str, List[TimeSlot]], key: str, time_slot: TimeSlot) -> None:
        """Remove a booking under `key`."""
        slots = slots_by_id.get(key)
        if slots is None:
            return
        slots.remove(time_slot)
        if not slots:
            del slots_by_id[key]
