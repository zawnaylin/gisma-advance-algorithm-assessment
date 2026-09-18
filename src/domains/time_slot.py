from dataclasses import dataclass

from domains.constraints import AVAILABLE_DAY, START_TIME, END_TIME


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """A block of whole hours on one teaching day, from `start_hour` to `end_hour`."""

    day: int
    start_hour: int
    end_hour: int

    def __post_init__(self) -> None:
        if self.day not in AVAILABLE_DAY:
            raise ValueError(f"Day {self.day} is not a valid school day.")

        if self.start_hour < START_TIME or self.end_hour > END_TIME:
            raise ValueError(
                f"Hours must be within {START_TIME}-{END_TIME}, got {self.start_hour}-{self.end_hour}."
            )

        if self.start_hour >= self.end_hour:
            raise ValueError(f"start_hour ({self.start_hour}) must be before end_hour ({self.end_hour}).")

    def overlaps(self, other: "TimeSlot") -> bool:
        """True when the two slots share any time on the same day."""
        if self.day != other.day:
            return False
        return self.start_hour < other.end_hour and other.start_hour < self.end_hour
