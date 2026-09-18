from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Professor:
    """A member of teaching staff."""

    id: str
    name: str = ""
