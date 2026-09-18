"""Scheduling constants: the teaching week and the oversized-room rule (goal 4)."""

from calendar import MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY

# First and last teaching hour, 24-hour clock
START_TIME = 9
END_TIME = 17

# Teaching days
AVAILABLE_DAY = (MONDAY,
                 TUESDAY,
                 WEDNESDAY,
                 THURSDAY,
                 FRIDAY)

# Longest a class may run
MAX_CLASS_DURATION = END_TIME - START_TIME

# A room with more than this many seats per student is oversized (goal 4)
OVERSIZE_FACTOR = 2
