import pytest

from domains.professor import Professor


def test_holds_its_values():
    professor = Professor("P001", "Dr. Turing")
    assert professor.id == "P001"
    assert professor.name == "Dr. Turing"


def test_name_is_optional():
    assert Professor("P001").name == ""


def test_professor_is_an_immutable_value():
    professor = Professor("P001", "Dr. Turing")
    assert professor == Professor("P001", "Dr. Turing")
    with pytest.raises(AttributeError):
        professor.name = "Dr. Hopper"
