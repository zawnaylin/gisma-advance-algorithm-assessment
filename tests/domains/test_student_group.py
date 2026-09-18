import pytest

from domains.class_information import ClassInformation
from domains.student_group import StudentGroup


def make_class(class_id="C0001"):
    return ClassInformation(class_id, "Intro to CS", number_of_students=18, professor_id="P001")


def test_rejects_empty_class_list():
    with pytest.raises(ValueError):
        StudentGroup("G-1", [])


def test_class_ids_reflects_membership():
    group = StudentGroup("G-1", [make_class("C0001"), make_class("C0002")])
    assert group.class_ids() == ["C0001", "C0002"]


def test_classes_cannot_be_mutated_from_outside():
    original = [make_class("C0001")]
    group = StudentGroup("G-1", original)

    with pytest.raises(AttributeError):
        group.classes.append(make_class("C0002"))

    original.append(make_class("C0003"))
    assert group.class_ids() == ["C0001"]


def test_size_defaults_to_unknown():
    assert StudentGroup("G-1", [make_class()]).size == 0


def test_rejects_negative_size():
    with pytest.raises(ValueError):
        StudentGroup("G-1", [make_class()], size=-1)
