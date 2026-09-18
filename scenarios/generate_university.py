"""Builds university.json: 5,000 students, 300 professors, 50 lecture halls.

Run from the repository root:  python scenarios/generate_university.py
"""

import json
import math
import random
from pathlib import Path

SEED = 2026
TOTAL_STUDENTS = 5000
PROFESSORS_PER_DEPARTMENT = 30
MAX_COHORT = 34

DEPARTMENTS = [
    ("CS", "Computer Science"),
    ("MATH", "Mathematics"),
    ("PHYS", "Physics"),
    ("CHEM", "Chemistry"),
    ("BIO", "Biology"),
    ("ECON", "Economics"),
    ("PSY", "Psychology"),
    ("ENG", "English Literature"),
    ("ART", "Art and Design"),
    ("LAW", "Law"),
]
LAB_DEPARTMENTS = {"CS", "PHYS", "CHEM", "BIO", "PSY"}

LECTURES = {
    1: ["Foundations of {}", "{} Methods I", "Introduction to {} Practice"],
    2: ["{} Methods II", "Topics in {}", "{} Theory"],
    3: ["Advanced {}", "Contemporary {}", "{} Research Methods"],
}
LECTURE_OVERRIDES = {("CS", 1): ["Intro to Programming", "Computer Systems", "Discrete Structures"]}

# (department, year, students, seminar title) - carved out of that year group
HONOURS = [
    ("ENG", 3, 10, "Poetry Seminar"),
    ("CS", 3, 12, "Quantum Computing Seminar"),
    ("LAW", 3, 11, "Moot Court Seminar"),
]

# (title, teaching department, attending year groups)
SERVICE_LECTURES = [
    ("Intro to Math", "MATH", [("CS", 1), ("PHYS", 1)]),
    ("Intro to Statistics", "MATH", [("ECON", 1), ("PSY", 1)]),
]

# 50 halls: (id prefix, capacity, how many)
ESTATE = [("AUD", 500, 1), ("H200", 200, 6), ("H100", 100, 4), ("R40", 40, 20), ("R25", 25, 10), ("R15", 15, 9)]


def year_group_sizes(rng):
    """Sizes of the 30 year groups, summing to exactly TOTAL_STUDENTS."""
    count = len(DEPARTMENTS) * 3
    base, extra = divmod(TOTAL_STUDENTS, count)
    sizes = [base + (1 if i < extra else 0) for i in range(count)]
    for i in range(0, count, 2):
        shift = rng.randint(0, 25)
        sizes[i] += shift
        sizes[i + 1] -= shift
    rng.shuffle(sizes)
    return sizes


def split(total, parts):
    """Split `total` into `parts` near-equal whole numbers."""
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def build():
    """Build the scenario as a JSON-ready dict of rooms, classes and student groups."""
    rng = random.Random(SEED)
    sizes = iter(year_group_sizes(rng))

    groups = []  # {"group_id", "size", "classes": []}
    by_year_group = {}
    for dept, _ in DEPARTMENTS:
        for year in (1, 2, 3):
            size = next(sizes)
            members = []
            for h_dept, h_year, h_size, _ in HONOURS:
                if (h_dept, h_year) == (dept, year):
                    size -= h_size
                    members.append({"group_id": f"G-{dept}-Y{year}-HON", "size": h_size, "classes": []})
            cohorts = split(size, math.ceil(size / MAX_COHORT))
            for index, cohort_size in enumerate(cohorts):
                letter = chr(ord("A") + index)
                members.append({"group_id": f"G-{dept}-Y{year}-{letter}", "size": cohort_size, "classes": []})
            by_year_group[(dept, year)] = members
            groups.extend(members)

    classes = []  # {"class_id", "name", "department", "duration_hours", "groups": [...]}

    def add_class(name, department, duration, attending):
        """Add a class and record it on each attending group."""
        class_id = f"C{len(classes) + 1:04d}"
        classes.append({"class_id": class_id, "name": name, "department": department,
                         "duration_hours": duration, "groups": attending})
        for group in attending:
            group["classes"].append(class_id)

    names = dict(DEPARTMENTS)
    for dept, name in DEPARTMENTS:
        for year in (1, 2, 3):
            members = by_year_group[(dept, year)]
            titles = LECTURE_OVERRIDES.get((dept, year)) or [t.format(name) for t in LECTURES[year]]
            for title in titles:
                add_class(f"{title} ({dept} Y{year})", dept, 2, members)
            for group in members:
                label = group["group_id"].rsplit("-", 1)[1]
                if label == "HON":
                    title = next(t for d, y, _, t in HONOURS if (d, y) == (dept, year))
                    add_class(f"{title} ({dept} Y{year})", dept, 2, [group])
                    continue
                practical = "Lab" if dept in LAB_DEPARTMENTS else "Workshop"
                add_class(f"{dept} Y{year} Seminar ({label})", dept, 1, [group])
                add_class(f"{dept} Y{year} {practical} ({label})", dept, 2, [group])

    for title, dept, year_groups in SERVICE_LECTURES:
        attending = [g for yg in year_groups for g in by_year_group[yg]]
        audience = " + ".join(f"{d} Y{y}" for d, y in year_groups)
        add_class(f"{title} ({audience})", dept, 2, attending)

    # 30 professors per department; classes dealt round-robin so all 300 teach.
    next_professor = {}
    for index, (dept, _) in enumerate(DEPARTMENTS):
        next_professor[dept] = [f"P{index * PROFESSORS_PER_DEPARTMENT + i + 1:03d}"
                                for i in range(PROFESSORS_PER_DEPARTMENT)]
    dealt = {dept: 0 for dept in names}
    out_classes = []
    for c in classes:
        dept = c["department"]
        professor = next_professor[dept][dealt[dept] % PROFESSORS_PER_DEPARTMENT]
        dealt[dept] += 1
        out_classes.append({
            "class_id": c["class_id"],
            "name": c["name"],
            "num_students": sum(g["size"] for g in c["groups"]),
            "professor_id": professor,
            "duration_hours": c["duration_hours"],
        })

    rooms = []
    for prefix, capacity, count in ESTATE:
        for i in range(count):
            rooms.append({"room_id": f"{prefix}-{i + 1:02d}", "capacity": capacity})

    return {
        "rooms": rooms,
        "classes": out_classes,
        "student_groups": [
            {"group_id": g["group_id"], "size": g["size"], "classes": g["classes"]} for g in groups
        ],
    }


def main():
    """Write university.json next to this script and print a summary."""
    scenario = build()
    path = Path(__file__).with_name("university.json")
    path.write_text(json.dumps(scenario, indent=2) + "\n")

    students = sum(g["size"] for g in scenario["student_groups"])
    professors = len({c["professor_id"] for c in scenario["classes"]})
    print(f"wrote {path.name}: {students} students, {professors} professors, "
          f"{len(scenario['rooms'])} rooms, {len(scenario['classes'])} classes, "
          f"{len(scenario['student_groups'])} cohorts")


if __name__ == "__main__":
    main()
