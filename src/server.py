import sys
import threading
from socket import *
from typing import List
from objs.packet import Packet
from objs.frame import Frame

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4


def create_packets(frame_no: int, data_arr: List[str]) -> List[Packet]:
    packet_no = 0
    packets: List[Packet] = []
    for data in data_arr:
        packets.append(Packet(frame_no, packet_no, len(data_arr) - 1, len(data), data))
        packet_no += 1
    return packets


def server_handler(con_socket, ad):
    frame_no = 0
    total_frames = 457
    while frame_no < 1:  # 1 for now, change to frames later
        frame_no += 1
        f = open("./assets/road480p/road_{}.jpeg".format(frame_no), "rb")
        frame = Frame(f.read())
        data_arr: List[str] = frame.to_data_arr(MAX_DATA_SIZE)
        packets: List[Packet] = create_packets(frame_no, data_arr)
        for p in packets:
            data = p.pack()
            con_socket.send(data)
            print("Sent ", p.to_dict())
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
