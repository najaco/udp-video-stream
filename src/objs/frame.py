from enum import Enum
from functools import total_ordering
BYTE_LOC = 4


class Frame:
    def __init__(self, data: str):
        self.data = data

    class Priority(Enum):
        LOW = 0b000
        NORMAL = 0b001
        IMPORTANT = 0b010
        CRITICAL = 0b011

        def __lt__(self, other):
            if self.__class__ is other.__class__:
                return self.value < other.value
            return NotImplemented

        def __gt__(self, other):
            if self.__class__ is other.__class__:
                return self.value > other.value
            return NotImplemented

        def __ge__(self, other):
            if self.__class__ is other.__class__:
                return self.value >= other.value
            return NotImplemented

        def __le__(self, other):
            if self.__class__ is other.__class__:
                return self.value <= other.value
            return NotImplemented

    @property
    def priority(self) -> Priority:
        priority_byte = self.data[BYTE_LOC] >> 5
        return self.Priority(priority_byte)
