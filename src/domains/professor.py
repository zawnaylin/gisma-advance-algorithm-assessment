from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Professor:
    id: str
    name: str = ""
