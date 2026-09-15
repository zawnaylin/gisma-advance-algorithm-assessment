from typing import List

from data.time_slot import TimeSlot


class Professor:
    def __init__(self, professor_id: str, name: str = ""):
        self._id = professor_id
        self._name = name
        self._assigned_slots: List[TimeSlot] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def assigned_slots(self) -> List[TimeSlot]:
        return list(self._assigned_slots)

    def is_available(self, time_slot: TimeSlot) -> bool:
        return not any(time_slot.overlaps(s) for s in self._assigned_slots)

    def assign(self, time_slot: TimeSlot) -> None:
        if not self.is_available(time_slot):
            raise ValueError(f"Professor {self._id} is already teaching during {time_slot}.")
        self._assigned_slots.append(time_slot)

    def __repr__(self) -> str:
        return f"Professor(id={self._id!r}, name={self._name!r})"
