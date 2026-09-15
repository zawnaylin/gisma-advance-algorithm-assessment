import pytest

from data.constraints import MAX_CLASS_DURATION
from domains.class_information import ClassInformation
from domains.room import Room


def make_class(**overrides):
    kwargs = dict(number_of_students=18, professor_id="P001")
    kwargs.update(overrides)
    return ClassInformation("C0001", "Intro to CS", **kwargs)


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


def test_duration_defaults_to_one_hour():
    assert make_class().duration_hours == 1


def test_accepts_a_multi_hour_duration():
    assert make_class(duration_hours=3).duration_hours == 3


def test_duration_may_fill_the_whole_school_day():
    assert make_class(duration_hours=MAX_CLASS_DURATION).duration_hours == MAX_CLASS_DURATION


@pytest.mark.parametrize("duration", [0, -1, MAX_CLASS_DURATION + 1])
def test_rejects_impossible_durations(duration):
    with pytest.raises(ValueError):
        make_class(duration_hours=duration)
