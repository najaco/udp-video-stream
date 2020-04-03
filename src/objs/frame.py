from .frame_priority import FramePriority

from enum import Enum

BYTE_LOC = 4


class Frame:
    def __init__(self, data: str):
        self.data = data

    class Priority(Enum):
        LOW = 0b000
        NORMAL = 0b001
        IMPORTANT = 0b010
        CRITICAL = 0b011

    @property
    def priority(self) -> Priority:
        priority_byte = self.data[BYTE_LOC] >> 5
        return self.Priority(priority_byte)
