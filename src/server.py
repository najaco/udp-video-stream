import math
import sys
import threading
import time
from objs.frame import Frame
from objs.packet import Packet
from socket import *
from typing import List

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4
SLEEP_TIME = .016 # equivalent to 60 fps


def create_packets(frame_no: int, data_arr: List[str]) -> List[Packet]:
    packet_no = 0
    packets: List[Packet] = []
    for data in data_arr:
        packets.append(Packet(frame_no, packet_no, len(data_arr), len(data), data))
        packet_no += 1
    return packets

def to_data_arr(data: str, max_data_size: int) -> List[str]:
    number_of_packets = math.ceil(len(data) / max_data_size)
    packet_data = [None] * number_of_packets
    for i in range(0, number_of_packets):
        if (i + 1) * max_data_size < len(data):
            packet_data[i] = data[i * max_data_size: (i + 1) * max_data_size]
        else:
            packet_data[i] = data[i * max_data_size:]
    return packet_data


def server_handler(con_socket, ad):
    frame_no = 0
    total_frames = 626
    while frame_no < total_frames:  # 1 for now, change to frames later
        frame_no += 1
        f = open("./assets/road480p/road_{}.jpeg".format(frame_no), "rb")
        frame = f.read()
        data_arr: List[str] = to_data_arr(frame, MAX_DATA_SIZE)
        packets: List[Packet] = create_packets(frame_no, data_arr)
        for p in packets:
            data = p.pack()
            con_socket.send(data)
            # print("Sent ", p.to_dict())
        time.sleep(SLEEP_TIME) # sleep
        print("Sent Frame #: {}".format(frame_no))
    con_socket.close()


usage = "usage: python " + sys.argv[0] + " [portno]"
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(usage)
        exit(1)

    serverPort = sys.argv[1]
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    serverSocket.bind(('', int(serverPort)))
    serverSocket.listen(8)
    while True:
        connectionSocket, addr = serverSocket.accept()
        threading.Thread(target=server_handler, args=(connectionSocket, addr)).start()
    serverSocket.close()
