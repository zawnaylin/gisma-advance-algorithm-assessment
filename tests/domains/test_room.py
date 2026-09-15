import pytest

from domains.room import Room


def test_rejects_non_positive_capacity():
    with pytest.raises(ValueError):
        Room("R-1", 0)
    with pytest.raises(ValueError):
        Room("R-1", -5)


@pytest.mark.parametrize("students, capacity, expected", [(20, 20, True), (21, 20, False), (0, 20, True)])
def test_has_capacity(students, capacity, expected):
    room = Room("R-1", capacity)
    assert room.has_capacity(students) is expected


def test_room_is_an_immutable_value():
    room = Room("R-1", 20)
    assert room == Room("R-1", 20)
    with pytest.raises(AttributeError):
        room.capacity = 50
