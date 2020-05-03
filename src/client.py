import configparser
import logging
import os
import shutil
import signal
import sys
import threading
import time
from os import path
from pathlib import Path
from socket import *
from typing import Dict

from objs import Frame
from objs.ack import Ack
from objs.frame_builder import FrameBuilder
from objs.metadata import Metadata
from objs.packet import Packet

config = configparser.ConfigParser()
config.read("config.ini")
MAX_PKT_SIZE: int = int(config["DEFAULT"]["MaxPacketSize"])
PRIORITY_THRESHOLD: Frame.Priority = Frame.Priority(
    int(config["DEFAULT"]["PriorityThreshold"])
)
CACHE_PATH: str = config["CLIENT"]["CachePath"]
FILE_WAIT_TIME: float = 0.005
FILE_MAX_WAIT_TIME: float = 0.03

frames: Dict[int, FrameBuilder] = {}


def writer(client_socket, meta_data: Metadata):
    logging.info("Writer Started")
    logging.info(
        "Receiving {} with {} frames".format(
            meta_data.file_name, meta_data.number_of_frames
        )
    )
    completed_frames = 0
    while completed_frames < meta_data.number_of_frames:
        msg_from = client_socket.recv(1024)
        if len(msg_from) == 0:
            break
        p: Packet = Packet.unpack(msg_from)
        if p is None:
            continue
        # check if frame # of packet is in frames here

        if p.frame_no not in frames:
            frames[p.frame_no] = FrameBuilder(
                n_expected_packets=p.total_seq_no, priority=p.priority
            )
        try:
            frames[p.frame_no].emplace(p.seq_no, p.data)
        except Exception:
            print("Error with frame no {}".format(p.frame_no))
        # check if frame is filled
        if frames[p.frame_no].is_complete():
            frame_to_save = open("./temp/{}.h264".format(p.frame_no), "wb+")
            frame_to_save.write(frames[p.frame_no].get_data_as_bytes())
            frame_to_save.close()
            if frames[p.frame_no].to_frame().priority >= PRIORITY_THRESHOLD:
                client_socket.send(Ack(p.frame_no).pack())
                logging.info("ACK {} Sent".format(p.frame_no))
            del frames[p.frame_no]  # delete frame now that it has been saved
            completed_frames += 1
    client_socket.close()
    logging.info("Writer Finished")


def reader(meta_data: Metadata):
    logging.info("Reader Started")
    frame_no = 1
    while not path.exists("{}{}.h264".format(CACHE_PATH, 1)):
        time.sleep(FILE_WAIT_TIME)
    while frame_no < meta_data.number_of_frames:
        logging.info("Waiting for {}{}.h264 exists".format(CACHE_PATH, frame_no))
        time_passed = 0
        while not path.exists("{}{}.h264".format(CACHE_PATH, frame_no)) and (
            time_passed < FILE_MAX_WAIT_TIME
            or (frame_no in frames and frames[frame_no].priority >= PRIORITY_THRESHOLD)
        ):
            time_passed += FILE_WAIT_TIME
            time.sleep(FILE_WAIT_TIME)  # force context switch

        if not path.exists(
            "{}{}.h264".format(CACHE_PATH, frame_no)
        ):  # skip if frame does not exist
            logging.warning("Skipping Frame {}".format(frame_no))
            frame_no += 1
            continue

        with open("{}{}.h264".format(CACHE_PATH, frame_no), "rb") as f:
            with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                stdout.write(f.read())
                stdout.flush()
        logging.info("Wrote {}{}.h264".format(CACHE_PATH, frame_no))
        os.remove("{}{}.h264".format(CACHE_PATH, frame_no))
        frame_no += 1
    logging.info("Reader Finished")


def set_up_dirs(cache_path: str):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            "{} must not already exist as a non directory".format(cache_path)
        )


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"


def main(argv: [str]):
    server_ip, server_port = argv[1], argv[2]
    set_up_dirs(CACHE_PATH)
    client_socket = socket(AF_INET, SOCK_STREAM)
    client_socket.connect((server_ip, int(server_port)))
    Path(CACHE_PATH).mkdir(
        parents=True, exist_ok=True
    )  # create directory if it does not exist
    meta_data_msg = client_socket.recv(1024)
    meta_data: Metadata = Metadata.unpack(meta_data_msg)
    logging.info(meta_data.to_dict())
    writer_thread = threading.Thread(target=writer, args=(client_socket, meta_data))
    reader_thread = threading.Thread(target=reader, args=(meta_data,))
    writer_thread.start()
    reader_thread.start()

    writer_thread.join()
    reader_thread.join()
    logging.info("Finished")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        exit(1)
    signal.signal(signal.SIGINT, clean_up)
    logging.basicConfig(filename=config["CLIENT"]["LogPath"], level=logging.INFO)
    logging.info(config)
    main(sys.argv)
