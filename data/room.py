from typing import List

from data.time_slot import TimeSlot


class Room:
    def __init__(self, room_id: str, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive.")

        self._id = room_id
        self._capacity = capacity
        self._assigned_slots: List[TimeSlot] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def assigned_slots(self) -> List[TimeSlot]:
        return list(self._assigned_slots)

    def has_capacity(self, number_of_students: int) -> bool:
        return number_of_students <= self._capacity

    def is_available(self, time_slot: TimeSlot) -> bool:
        return not any(time_slot.overlaps(s) for s in self._assigned_slots)

    def assign(self, time_slot: TimeSlot) -> None:
        if not self.is_available(time_slot):
            raise ValueError(f"Room {self._id} is already booked during {time_slot}.")
        self._assigned_slots.append(time_slot)

    def __repr__(self) -> str:
        return f"Room(id={self._id!r}, capacity={self._capacity})"
