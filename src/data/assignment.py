from dataclasses import dataclass

from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.time_slot import TimeSlot


@dataclass(frozen=True)
class ClassAssignment:
    """One placed class: its room, professor and time slot."""

    class_info: ClassInformation
    room: Room
    professor: Professor
    time_slot: TimeSlot
