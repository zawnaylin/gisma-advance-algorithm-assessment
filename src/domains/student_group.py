from dataclasses import dataclass
from typing import List, Sequence

from domains.class_information import ClassInformation


@dataclass(eq=False)
class StudentGroup:
    id: str
    classes: Sequence[ClassInformation]

    def __post_init__(self) -> None:
        if not self.classes:
            raise ValueError("A student group must have at least one class.")
        self.classes = tuple(self.classes)

    def class_ids(self) -> List[str]:
        return [c.id for c in self.classes]

    def __repr__(self) -> str:
        return f"StudentGroup(id={self.id!r}, classes={self.class_ids()!r})"
