from .packet import Packet
from typing import List
import math


class Frame:
    def __init__(self, data: str = ""):
        self.data: str = data

    def to_data_arr(self, max_data_size: int) -> List[str]:
        number_of_packets = math.ceil(len(self.data) / max_data_size)
        print("Generating ", number_of_packets)
        packet_data = [None] * number_of_packets
        for i in range(0, number_of_packets):
            if (i + 1) * max_data_size < len(self.data):
                packet_data[i] = self.data[i * max_data_size: (i + 1) * max_data_size]
            else:
                packet_data[i] = self.data[i * max_data_size:]
        return packet_data

    def to_dict(self):
        return {
            "data": self.data
        }
