import pytest

from data.class_information import ClassInformation
from data.student_group import StudentGroup


def make_class(class_id="C0001"):
    return ClassInformation(class_id, "Intro to CS", number_of_students=18, professor_id="P001")


def test_rejects_empty_class_list():
    with pytest.raises(ValueError):
        StudentGroup("G-1", [])


def test_class_ids_reflects_membership():
    group = StudentGroup("G-1", [make_class("C0001"), make_class("C0002")])
    assert group.class_ids() == ["C0001", "C0002"]


def test_classes_property_is_a_copy():
    original = [make_class("C0001")]
    group = StudentGroup("G-1", original)
    group.classes.append(make_class("C0002"))
    assert group.class_ids() == ["C0001"]
