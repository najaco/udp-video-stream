import configparser
import logging
import os
import shutil
import signal
import sys
import threading
import time
import random
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
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 6
PRIORITY_THRESHOLD: Frame.Priority = Frame.Priority(
    int(config["DEFAULT"]["PriorityThreshold"])
)
CACHE_PATH: str = config["SERVER"]["CachePath"]
SLEEP_TIME = float(config["SERVER"]["SleepTime"])
RETR_TIME = int(config["SERVER"]["RetransmissionTime"])
RETR_INTERVAL = float(config["SERVER"]["RetransmissionInterval"])
DROP_RATE = .005

def create_packets(frame: Frame) -> List[Packet]:
    data_arr: List[str] = frame.to_data_arr(MAX_DATA_SIZE)
    packet_no = 0
    packets: List[Packet] = []
    for data in data_arr:
        packets.append(
            Packet(
                frame_no=frame.frame_no,
                seq_no=packet_no,
                total_seq_no=len(data_arr),
                size=len(data),
                priority=frame.priority,
                data=data,
            )
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
            if frame_retr_times.contains(a.frame_no):
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
                    frame_retr_times.insert(
                        k=RETR_TIME, e=i
                    )  # re insert frame to delta list
                    for packet in create_packets(frames[i]):
                        if random.random() >= DROP_RATE:
                            con_socket.send(packet.pack())
                logging.info("Retransmitted frame {}".format(i))

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
        if frame.priority >= PRIORITY_THRESHOLD or frame_no == 1:

            critical_frame_acks[frame_no] = False
            frame_retr_times.insert(k=RETR_TIME, e=frame_no)

        # send_frame(frame, frame_no, con_socket)
        packets: List[Packet] = create_packets(frame)
        for p in packets:
            if random.random() >= DROP_RATE:
                con_socket.send(p.pack())

        time.sleep(SLEEP_TIME)  # sleep
        logging.info("Sent Frame #: {}".format(frame_no))
    reader_thread.join()
    retransmitter_thread.join()
    con_socket.close()
    logging.info("Handler Finished")


def cl_ffmpeg(file_path: str, cache_path: str):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )
    cmd = "ffmpeg -i {} -f image2 -c:v copy -bsf h264_mp4toannexb {}%d.h264".format(
        file_path, cache_path
    )
    os.system(cmd)


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


usage = "usage: python " + sys.argv[0] + " [portno] [file]"


def main(argv: [str]):
    server_port = argv[1]
    file_path = argv[2]

    cl_ffmpeg(file_path, CACHE_PATH)

    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server_socket.bind(("", int(server_port)))
    server_socket.listen(8)
    number_of_frames = len(os.listdir(CACHE_PATH)) - 1
    while True:
        connection_socket, addr = server_socket.accept()
        threading.Thread(
            target=server_handler,
            args=(connection_socket, addr, CACHE_PATH, 0, number_of_frames),
        ).start()
    server_socket.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        exit(1)

    signal.signal(signal.SIGINT, clean_up)
    logging.basicConfig(filename=config["SERVER"]["LogPath"], level=logging.INFO)
    main(sys.argv)
