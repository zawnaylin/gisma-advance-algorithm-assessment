from data.constraints import AVAILABLE_DAY, START_TIME, END_TIME


class TimeSlot:
    def __init__(self, day: int, start_hour: int, end_hour: int):
        if day not in AVAILABLE_DAY:
            raise ValueError(f"Day {day} is not a valid school day.")

        if start_hour < START_TIME or end_hour > END_TIME:
            raise ValueError(
                f"Hours must be within {START_TIME}-{END_TIME}, got {start_hour}-{end_hour}."
            )

        if start_hour >= end_hour:
            raise ValueError(f"start_hour ({start_hour}) must be before end_hour ({end_hour}).")

        self.day = day
        self.start_hour = start_hour
        self.end_hour = end_hour

    def overlaps(self, other: "TimeSlot") -> bool:
        if self.day != other.day:
            return False
        return self.start_hour < other.end_hour and other.start_hour < self.end_hour

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeSlot):
            return NotImplemented
        return (self.day, self.start_hour, self.end_hour) == (other.day, other.start_hour, other.end_hour)

    def __hash__(self) -> int:
        return hash((self.day, self.start_hour, self.end_hour))

    def __repr__(self) -> str:
        return f"TimeSlot(day={self.day}, {self.start_hour}-{self.end_hour})"
