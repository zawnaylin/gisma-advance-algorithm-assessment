import json

import pytest

from data.loader import Scenario, available_scenarios, load_file, load_scenario


def test_baseline_is_always_available():
    assert "baseline" in available_scenarios()


@pytest.mark.parametrize("name", available_scenarios())
def test_every_scenario_loads(name):
    scenario = load_scenario(name)

    assert isinstance(scenario, Scenario)
    assert scenario.name == name
    assert scenario.rooms and scenario.classes and scenario.professors


def test_unknown_scenario_is_rejected():
    with pytest.raises(FileNotFoundError):
        load_scenario("does-not-exist")


def test_professors_cover_every_class():
    scenario = load_scenario()
    professor_ids = {p.id for p in scenario.professors}

    assert {c.professor_id for c in scenario.classes} <= professor_ids


def test_groups_hold_the_same_class_objects():
    scenario = load_scenario()
    by_id = {c.id: c for c in scenario.classes}

    for group in scenario.groups:
        for class_info in group.classes:
            assert by_id[class_info.id] is class_info


def test_duration_defaults_to_one_hour_when_absent(tmp_path):
    raw = {
        "rooms": [{"room_id": "R-1", "capacity": 20}],
        "classes": [{"class_id": "C1", "name": "Legacy", "num_students": 10, "professor_id": "P1"}],
        "student_groups": [],
    }
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(raw))

    scenario = load_file(path)

    assert scenario.classes[0].duration_hours == 1
    assert scenario.name == "legacy"


def test_group_sizes_are_read_and_counted(tmp_path):
    raw = {
        "rooms": [{"room_id": "R-1", "capacity": 40}],
        "classes": [{"class_id": "C1", "name": "Intro", "num_students": 55, "professor_id": "P1"}],
        "student_groups": [
            {"group_id": "G-A", "size": 30, "classes": ["C1"]},
            {"group_id": "G-B", "size": 25, "classes": ["C1"]},
        ],
    }
    path = tmp_path / "sized.json"
    path.write_text(json.dumps(raw))

    scenario = load_file(path)

    assert [g.size for g in scenario.groups] == [30, 25]
    assert scenario.students == 55
