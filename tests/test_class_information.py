import pytest

from data.class_information import ClassInformation
from data.room import Room


def test_rejects_negative_students():
    with pytest.raises(ValueError):
        ClassInformation("C0001", "Intro to CS", number_of_students=-1, professor_id="P001")


def test_stores_constructor_values():
    class_info = ClassInformation("C0001", "Intro to CS", number_of_students=18, professor_id="P001")
    assert class_info.id == "C0001"
    assert class_info.name == "Intro to CS"
    assert class_info.number_of_students == 18
    assert class_info.professor_id == "P001"


def test_fits_in_room_within_capacity():
    class_info = ClassInformation("C0001", "Intro to CS", number_of_students=18, professor_id="P001")
    assert class_info.fits_in(Room("R-1", 20))
    assert not class_info.fits_in(Room("R-1", 17))


def test_zero_student_class_fits_any_room():
    class_info = ClassInformation("C0001", "Cancelled", number_of_students=0, professor_id="P001")
    assert class_info.fits_in(Room("R-1", 1))
