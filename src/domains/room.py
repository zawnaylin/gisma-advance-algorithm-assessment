from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Room:
    """A lecture hall and its number of seats."""

    id: str
    capacity: int

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive.")

    def has_capacity(self, number_of_students: int) -> bool:
        """True when the room seats that many students."""
        return number_of_students <= self.capacity
