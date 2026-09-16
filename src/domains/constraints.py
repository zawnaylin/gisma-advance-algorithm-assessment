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
