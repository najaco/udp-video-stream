from typing import List, Dict
import struct

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4


class Packet:
    def __init__(self, frame_no: int, seq_no: int, total_seq_no: int, size: int, data: str):
        self.frame_no: int = frame_no
        self.seq_no: int = seq_no
        self.total_seq_no: int = total_seq_no
        self.size: int = size
        self.data: str = data

    def pack(self):
        return struct.pack("!IIII{}s".format(self.size), self.frame_no, self.seq_no, self.total_seq_no, self.size,
                           self.data)

    # {}x -> MAX_PKT_SIZE - self.size
    # was removed

    def to_dict(self) -> Dict:
        return {
            "frame_no": self.frame_no,
            "seq_no": self.seq_no,
            "total_seq_no": self.total_seq_no,
            "size": self.size,
            "data": self.data
        }
    # @staticmethod
    # def unpack(bytes: str) -> Packet:
    #     tuple = struct.unpack("IIIIs")
    #
    #     return Packet(tuple[0], tup, 0, 0, "")
