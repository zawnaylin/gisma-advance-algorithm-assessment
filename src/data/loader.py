"""Reads a scenario file into domain objects.

A scenario is one complete instance of the problem: the rooms available, the
classes to place, and the student groups that must not collide. Professors are
implied by the classes that name them.
"""

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
    name: str
    rooms: List[Room]
    classes: List[ClassInformation]
    professors: List[Professor]
    groups: List[StudentGroup]

    def __repr__(self) -> str:
        return (
            f"Scenario(name={self.name!r}, rooms={len(self.rooms)}, "
            f"classes={len(self.classes)}, professors={len(self.professors)}, "
            f"groups={len(self.groups)})"
        )


def available_scenarios() -> List[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json")) if SCENARIO_DIR.is_dir() else []


def load_scenario(name: str = "baseline") -> Scenario:
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown scenario {name!r}; expected one of {available_scenarios()}.")
    return load_file(path, name=name)


def load_file(path: Path, name: str | None = None) -> Scenario:
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
        StudentGroup(g["group_id"], [classes_by_id[cid] for cid in g["classes"]])
        for g in raw.get("student_groups", [])
    ]

    return Scenario(name or Path(path).stem, rooms, classes, professors, groups)
