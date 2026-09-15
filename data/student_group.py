from typing import List

from data.class_information import ClassInformation


class StudentGroup:
    def __init__(self, group_id: str, classes: List[ClassInformation]):
        if not classes:
            raise ValueError("A student group must have at least one class.")

        self._id = group_id
        self._classes = classes

    @property
    def id(self) -> str:
        return self._id

    @property
    def classes(self) -> List[ClassInformation]:
        return list(self._classes)

    def class_ids(self) -> List[str]:
        return [c.id for c in self._classes]

    def __repr__(self) -> str:
        return f"StudentGroup(id={self._id!r}, classes={self.class_ids()!r})"
