from dataclasses import dataclass

from domains.constraints import MAX_CLASS_DURATION
from domains.room import Room


@dataclass(frozen=True, slots=True)
class ClassInformation:
    """A class to schedule: its size, professor and length in hours."""

    id: str
    name: str
    number_of_students: int
    professor_id: str
    duration_hours: int = 1

    def __post_init__(self) -> None:
        if self.number_of_students < 0:
            raise ValueError("number_of_students cannot be negative.")

        if self.duration_hours < 1:
            raise ValueError("duration_hours must be at least one hour.")

        if self.duration_hours > MAX_CLASS_DURATION:
            raise ValueError(
                f"duration_hours cannot exceed the {MAX_CLASS_DURATION}-hour school day, "
                f"got {self.duration_hours}."
            )

    def fits_in(self, room: Room) -> bool:
        """True when the room has a seat for every student."""
        return room.has_capacity(self.number_of_students)
