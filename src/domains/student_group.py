from dataclasses import dataclass
from typing import List, Sequence

from domains.class_information import ClassInformation


@dataclass(eq=False)
class StudentGroup:
    """A cohort of students who all attend the same classes."""

    id: str
    classes: Sequence[ClassInformation]
    size: int = 0  # number of students; 0 when unknown

    def __post_init__(self) -> None:
        if not self.classes:
            raise ValueError("A student group must have at least one class.")
        if self.size < 0:
            raise ValueError("size cannot be negative.")
        self.classes = tuple(self.classes)

    def class_ids(self) -> List[str]:
        """Ids of the group's classes."""
        return [c.id for c in self.classes]

    def __repr__(self) -> str:
        return f"StudentGroup(id={self.id!r}, size={self.size}, classes={self.class_ids()!r})"
