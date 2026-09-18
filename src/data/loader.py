"""Loads scenario JSON files into domain objects."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from domains.class_information import ClassInformation
from domains.professor import Professor
from domains.room import Room
from domains.student_group import StudentGroup

SCENARIO_DIR = Path(__file__).parents[2] / "scenarios"


@dataclass(frozen=True)
class Scenario:
    """One problem instance as read from a file."""

    name: str
    rooms: List[Room]
    classes: List[ClassInformation]
    professors: List[Professor]
    groups: List[StudentGroup]

    @property
    def students(self) -> int:
        """Total students across all groups; 0 when the file gives no group sizes."""
        return sum(group.size for group in self.groups)

    def __repr__(self) -> str:
        return (
            f"Scenario(name={self.name!r}, rooms={len(self.rooms)}, "
            f"classes={len(self.classes)}, professors={len(self.professors)}, "
            f"groups={len(self.groups)})"
        )


def available_scenarios() -> List[str]:
    """Names of the scenario files in `scenarios/`, sorted."""
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json")) if SCENARIO_DIR.is_dir() else []


def load_scenario(name: str = "baseline") -> Scenario:
    """Load a scenario from `scenarios/` by name.

    Raises:
        FileNotFoundError: if there is no scenario with that name.
    """
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown scenario {name!r}; expected one of {available_scenarios()}.")
    return load_file(path, name=name)


def load_file(path: Path, name: str | None = None) -> Scenario:
    """Load a scenario from a JSON file.

    Args:
        path: the JSON file.
        name: the scenario name; defaults to the file name without extension.
    """
    raw = json.loads(Path(path).read_text())

    rooms = [Room(r["room_id"], r["capacity"]) for r in raw["rooms"]]
    classes = [
        ClassInformation(
            c["class_id"],
            c["name"],
            c["num_students"],
            c["professor_id"],
            c.get("duration_hours", 1),
        )
        for c in raw["classes"]
    ]

    classes_by_id = {c.id: c for c in classes}
    professors = [Professor(pid) for pid in sorted({c.professor_id for c in classes})]
    groups = [
        StudentGroup(g["group_id"], [classes_by_id[cid] for cid in g["classes"]], g.get("size", 0))
        for g in raw.get("student_groups", [])
    ]

    return Scenario(name or Path(path).stem, rooms, classes, professors, groups)
