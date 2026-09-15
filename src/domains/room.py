from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Room:
    id: str
    capacity: int

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive.")

    def has_capacity(self, number_of_students: int) -> bool:
        return number_of_students <= self.capacity
