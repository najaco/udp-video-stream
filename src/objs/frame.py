from .priority import Priority

from enum import Enum

BYTE_LOC = 4


class Frame:
    def __init__(self, data: str):
        self.data = data
    #
    # class Priority(Enum):
    #     LOW = 0b000
    #     NORMAL = 0b001
    #     IMPORTANT = 0b010
    #     CRITICAL = 0b011
    #
    #     @staticmethod
    #     def determine_priority(data: str):
    #         priority_byte = ord(data[BYTE_LOC]) >> 1
    #         return Priority(priority_byte)

    @property
    def get_priority(self) -> Priority:
        return Priority.determine_priority(self.data)
