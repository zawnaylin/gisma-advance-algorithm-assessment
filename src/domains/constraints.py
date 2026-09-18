"""The rules a master schedule must follow.

Hard - a schedule that breaks any of these is unusable:

1. No person is in two classes at once.
   - a professor teaches one class at a time;
   - a student group attends one class at a time. Two classes that share a
     group are connected even when their professors differ: if Year 1 CS takes
     both Intro to Math and Intro to Programming, those two cannot overlap.
2. No room is double-booked.
3. Every class fits inside its assigned room.

Soft - the schedule is judged on it, but it may be broken when nothing better
is free:

4. Do not waste resources: no heating a 500-seat auditorium for a 10-person
   seminar. A placement counts as oversized when the room has more than
   OVERSIZE_FACTOR seats per student.

Every class also runs inside the teaching week defined below.
"""

from calendar import MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY

# The start time and end time for the school, uses 24-hour form
START_TIME = 9
END_TIME = 17

# Day which the class exists
AVAILABLE_DAY = (MONDAY,
                 TUESDAY,
                 WEDNESDAY,
                 THURSDAY,
                 FRIDAY)

# Longest a single class may run, bounded by the length of the school day
MAX_CLASS_DURATION = END_TIME - START_TIME

# Goal 4: a room with more than this many seats per student is oversized
OVERSIZE_FACTOR = 2
