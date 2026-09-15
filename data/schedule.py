from typing import Dict, Iterable, List

from data.assignment import ClassAssignment
from data.class_information import ClassInformation
from data.professor import Professor
from data.room import Room
from data.student_group import StudentGroup
from data.time_slot import TimeSlot


class Schedule:
    def __init__(self):
        self._assignments: List[ClassAssignment] = []
        self._assignment_by_class_id: Dict[str, ClassAssignment] = {}

    @property
    def assignments(self) -> List[ClassAssignment]:
        return list(self._assignments)

    def assignment_for(self, class_id: str) -> ClassAssignment | None:
        return self._assignment_by_class_id.get(class_id)

    def check_capacity(self, class_info: ClassInformation, room: Room) -> bool:
        return class_info.fits_in(room)

    def check_room_available(self, room: Room, time_slot: TimeSlot) -> bool:
        return room.is_available(time_slot)

    def check_professor_available(self, professor: Professor, time_slot: TimeSlot) -> bool:
        return professor.is_available(time_slot)

    def check_group_available(self, group: StudentGroup, time_slot: TimeSlot) -> bool:
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
        violations = self.validate(class_info, room, professor, time_slot, groups)
        if violations:
            raise ValueError("; ".join(violations))

        room.assign(time_slot)
        professor.assign(time_slot)

        assignment = ClassAssignment(class_info=class_info, room=room, professor=professor, time_slot=time_slot)
        self._assignments.append(assignment)
        self._assignment_by_class_id[class_info.id] = assignment
        return assignment
