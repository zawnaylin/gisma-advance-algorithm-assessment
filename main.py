from calendar import MONDAY

from data.class_information import ClassInformation
from data.professor import Professor
from data.room import Room
from data.schedule import Schedule
from data.student_group import StudentGroup
from data.time_slot import TimeSlot


def main() -> None:
    room = Room("R-100", capacity=20)
    professor = Professor("P001", "Dr. Turing")
    class_info = ClassInformation("C0001", "Intro to CS", number_of_students=18, professor_id=professor.id)
    group = StudentGroup("G-CS-Y1-A", [class_info])

    schedule = Schedule()
    slot = TimeSlot(MONDAY, 9, 11)

    assignment = schedule.add_assignment(class_info, room, professor, slot, groups=[group])
    print(f"Assigned {assignment.class_info.name} to {assignment.room.id} on {assignment.time_slot}")

    conflicting_slot = TimeSlot(MONDAY, 10, 12)
    violations = schedule.validate(class_info, room, professor, conflicting_slot, groups=[group])
    print(f"Conflicts for an overlapping slot: {violations}")


if __name__ == "__main__":
    main()
