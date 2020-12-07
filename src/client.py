import argparse
import configparser
import logging
import os
import shutil
import signal
import subprocess
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
LOG_PATH: Path = Path(config["CLIENT"]["LogPath"])
FILE_WAIT_TIME: float = float(config["CLIENT"]["FileWaitTime"])
FILE_MAX_WAIT_TIME: float = float(config["CLIENT"]["FileMaxWaitTime"])

frames: Dict[int, FrameBuilder] = {}


def get_vlc_path_for_current_platform(platform: str = sys.platform) -> Path:
    if platform == "linux" or platform == "linux2":
        return Path('vlc')
    elif platform == "darwin":
        return Path('/Applications/VLC.app/Contents/MacOS/VLC')
    elif platform == "win32":
        return Path('%PROGRAMFILES%\\VideoLAN\\VLC\\vlc.exe')


def writer(client_socket, meta_data: Metadata, server_addr_port):
    logging.info("Writer Started")
    logging.info(
        "Receiving {} with {} frames".format(
            meta_data.file_name, meta_data.number_of_frames
        )
    )
    completed_frames = 0
    while completed_frames < meta_data.number_of_frames:
        msg_from = client_socket.recv(1024)
        logging.info(f"Received Message: {msg_from}")
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
            # logging.info(f"Detected Beginning of Frame: {p.frame_no} at {int(time.time() * 1000)}ms")
            frame_to_save = open("{}{}.h264".format(CACHE_PATH, p.frame_no), "wb+")
            frame_to_save.write(frames[p.frame_no].get_data_as_bytes())
            frame_to_save.close()
            if frames[p.frame_no].to_frame().priority >= PRIORITY_THRESHOLD:
                client_socket.sendto(Ack(p.frame_no).pack(), server_addr_port)
                logging.info(f"ACK {p.frame_no} Sent at {time.time()}ms")
            del frames[p.frame_no]  # delete frame now that it has been saved
            completed_frames += 1
    client_socket.close()
    logging.info("Writer Finished")


def reader(meta_data: Metadata):
    logging.info("Reader Started")
    vlc_path: Path = get_vlc_path_for_current_platform()
    if not vlc_path.exists():
        logging.error(f"vlc was not found at {str(vlc_path)}")
        return
    vlc_process = subprocess.Popen(
        [str(vlc_path), "--demux", "h264", "-"],
        stdin=subprocess.PIPE,
    )
    frame_no = 1
    while not path.exists(f"{CACHE_PATH}{1}.h264"):
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
                f"{CACHE_PATH}{frame_no}.h264"
        ):  # skip if frame does not exist
            logging.warning(f"Skipping Frame {frame_no}")
            frame_no += 1
            continue

        with open(f"{CACHE_PATH}{frame_no}.h264", "rb") as f:
            vlc_process.stdin.write(f.read())
            logging.info(f"Detected Beginning of Frame: {frame_no} at {int(time.time() * 1000)}ms")
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

if __name__ == "__main__":
    signal.signal(signal.SIGINT, clean_up)

    parser = argparse.ArgumentParser(description="QUIC VideoStreamServer server")
    parser.add_argument(
        "app",
        type=str,
        nargs="?",
        default="demo:app",
        help="the ASGI application as <module>:<attribute>",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4433,
        help="listen on the specified port (defaults to 4433)",
    )
    parser.add_argument(
        "-l",
        "--log",
        type=str,
        default=LOG_PATH,
        help="file to send logging information to",
    )
    args = parser.parse_args()

    log_path: Path = Path(args.log)
    logging.basicConfig(filename=str(log_path), level=logging.INFO)

    server_ip, server_port = args.host, int(args.port)
    set_up_dirs(CACHE_PATH)

    UDP = True  # TODO SWITCH TO CLA
    logging.info(f"Creating socket for {args.host} port {args.port}")
    client_socket = socket(AF_INET, SOCK_DGRAM if UDP else SOCK_STREAM)
    # if not UDP:
    #     client_socket.connect((server_ip, int(server_port)))
    logging.info("Socket Connected!")
    client_socket.sendto(b"Send me files!", (server_ip, server_port))
    Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)  # create directory if it does not exist
    meta_data_msg = client_socket.recv(1024)
    meta_data: Metadata = Metadata.unpack(meta_data_msg)
    logging.info(meta_data.to_dict())
    writer_thread = threading.Thread(target=writer, args=(client_socket, meta_data, (server_ip, server_port)))
    reader_thread = threading.Thread(target=reader, args=(meta_data, ))
    writer_thread.start()
    reader_thread.start()

    writer_thread.join()
    reader_thread.join()
    logging.info("Finished")
