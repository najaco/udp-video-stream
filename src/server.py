import configparser
import logging
import os
import sys
import threading
import time
from socket import *
from typing import List

from delta_list.delta_list import DeltaList
from objs.ack import Ack
from objs.frame import Frame
from objs.metadata import Metadata
from objs.packet import Packet

config = configparser.ConfigParser()
config.read("config.ini")
MAX_PKT_SIZE: int = int(config["DEFAULT"]["MaxPacketSize"])
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4
PRIORITY_THRESHOLD: Frame.Priority = Frame.Priority(
    int(config["DEFAULT"]["PriorityThreshold"])
)
CACHE_PATH: str = config["SERVER"]["CachePath"]
SLEEP_TIME = float(config["SERVER"]["SleepTime"])
RETR_TIME = int(config["SERVER"]["RetransmissionTime"])
RETR_INTERVAL = int(config["SERVER"]["RetransmissionInterval"])


def create_packets(frame: Frame) -> List[Packet]:
    data_arr: List[str] = frame.to_data_arr(MAX_DATA_SIZE)
    packet_no = 0
    packets: List[Packet] = []
    for data in data_arr:
        packets.append(
            Packet(frame.frame_no, packet_no, len(data_arr), len(data), data)
        )
        packet_no += 1
    return packets


def server_handler(con_socket, ad, path_to_frames, starting_frame, total_frames):
    logging.info("Handler Started")
    frame_no = starting_frame
    meta_data = Metadata(file_name=path_to_frames, number_of_frames=total_frames)
    frames = {}
    critical_frame_acks = {}
    frame_retr_times: DeltaList[int] = DeltaList()

    def reader() -> None:
        logging.info("Reader Started")
        while True:
            msg_from = con_socket.recv(1024)
            if len(msg_from) == 0:
                break
            a: Ack = Ack.unpack(msg_from)
            critical_frame_acks[a.frame_no] = True
            # remove frame from dlist here
            frame_retr_times.remove(a.frame_no)
            logging.info("ACK {}".format(a.frame_no))
        logging.info("Reader Finished")

    def retransmitter(reader_thread) -> None:
        logging.info("Retransmitter Started")
        while reader_thread.is_alive():
            frame_retr_times.decrement_key()
            ready_frames: List[int] = frame_retr_times.remove_all_ready()
            for i in ready_frames:
                logging.info("Retransmitting frame {}".format(i))
                if i in critical_frame_acks and critical_frame_acks[i] is False:
                    for packet in create_packets(frames[i]):
                        con_socket.send(packet.pack())

            time.sleep(RETR_INTERVAL)
        logging.info("Retransmitter Finished")

    reader_thread = threading.Thread(target=reader, args=())
    retransmitter_thread = threading.Thread(target=retransmitter, args=(reader_thread,))
    reader_thread.start()
    retransmitter_thread.start()

    con_socket.send(meta_data.pack())
    time.sleep(SLEEP_TIME)
    while frame_no < total_frames:  # 1 for now, change to frames later
        frame_no += 1
        f = open("{}{}.h264".format(path_to_frames, frame_no), "rb")

        frame = Frame(f.read(), frame_no)
        frames[frame_no] = frame
        if frame.priority >= PRIORITY_THRESHOLD:  # add support for >= later
            critical_frame_acks[frame_no] = False
            frame_retr_times.insert(k=RETR_TIME, e=frame_no)

        # send_frame(frame, frame_no, con_socket)
        packets: List[Packet] = create_packets(frame)
        for p in packets:
            data = p.pack()
            con_socket.send(data)

        time.sleep(SLEEP_TIME)  # sleep
        logging.info("Sent Frame #: {}".format(frame_no))
    reader_thread.join()
    retransmitter_thread.join()
    con_socket.close()
    logging.info("Handler Finished")


usage = "usage: python " + sys.argv[0] + " [portno]"


def main():
    server_port = sys.argv[1]
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server_socket.bind(("", int(server_port)))
    server_socket.listen(8)
    path = "./assets/road480p/"
    number_of_frames = len(os.listdir(path)) - 1  # - 1 needed?
    while True:
        connection_socket, addr = server_socket.accept()
        threading.Thread(
            target=server_handler,
            args=(connection_socket, addr, path, 0, number_of_frames),
        ).start()
    server_socket.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(usage)
        exit(1)
    logging.basicConfig(filename=config["SERVER"]["LogPath"], level=logging.INFO)
    main()
