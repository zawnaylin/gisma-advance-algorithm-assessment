from dataclasses import dataclass

from data.class_information import ClassInformation
from data.professor import Professor
from data.room import Room
from data.time_slot import TimeSlot


@dataclass(frozen=True)
class ClassAssignment:
    class_info: ClassInformation
    room: Room
    professor: Professor
    time_slot: TimeSlot
