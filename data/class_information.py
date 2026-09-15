from data.room import Room


class ClassInformation:
    def __init__(self, class_id: str, name: str, number_of_students: int, professor_id: str):
        if number_of_students < 0:
            raise ValueError("number_of_students cannot be negative.")

        self._id = class_id
        self._name = name
        self._number_of_students = number_of_students
        self._professor_id = professor_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def number_of_students(self) -> int:
        return self._number_of_students

    @property
    def professor_id(self) -> str:
        return self._professor_id

    def fits_in(self, room: Room) -> bool:
        return room.has_capacity(self._number_of_students)

    def __repr__(self) -> str:
        return (
            f"ClassInformation(id={self._id!r}, name={self._name!r}, "
            f"number_of_students={self._number_of_students}, professor_id={self._professor_id!r})"
        )

    