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
from typing import Dict, Set

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
    logging.info(f"Receiving {meta_data.file_name} with {meta_data.number_of_frames} frames")
    completed_frames = 0
    already_completed_frames: Set[int] = set()
    while completed_frames < meta_data.number_of_frames:
        msg_from = client_socket.recv(1024)
        # logging.info(f"Received Message: {msg_from}")
        if len(msg_from) == b"END":
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
            logging.error(f"Error with frame no {p.frame_no}")
        # check if frame is filled
        if frames[p.frame_no].is_complete():
            # logging.info(f"Detected Beginning of Frame: {p.frame_no} at {int(time.time() * 1000)}ms")
            frame_to_save = open(f"{CACHE_PATH}{p.frame_no}.h264", "wb+")
            frame_to_save.write(frames[p.frame_no].get_data_as_bytes())
            frame_to_save.close()
            if frames[p.frame_no].to_frame().priority >= PRIORITY_THRESHOLD or frames[
                p.frame_no].to_frame().priority == Frame.Priority.START:
                client_socket.sendto(Ack(p.frame_no).pack(), server_addr_port)
                logging.info(f"ACK {p.frame_no} Sent at {int(time.time() * 1000)}ms")
            del frames[p.frame_no]  # delete frame now that it has been saved
            if p.frame_no not in already_completed_frames:
                logging.info(f"Saved {p.frame_no}")
                # logging.info(f"Frames = {list(frames.keys())}")
                completed_frames += 1
            already_completed_frames.add(p.frame_no)

    logging.info("Writer Finished")
    logging.info(f"Completed {completed_frames} / {meta_data.number_of_frames} frames")


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
    logging.info("VLC started, waiting for frames")
    frame_no = 1
    while not path.exists(f"{CACHE_PATH}{1}.h264"):
        time.sleep(FILE_WAIT_TIME)
    while frame_no < meta_data.number_of_frames:
        logging.info(f"Waiting for {CACHE_PATH}{frame_no}.h264 exists")
        time_passed = 0
        while not path.exists(f"{CACHE_PATH}{frame_no}.h264") and (
                time_passed < FILE_MAX_WAIT_TIME
        #        or (frame_no in frames and (
        #         frames[frame_no].priority >= PRIORITY_THRESHOLD or frames[frame_no].priority == Frame.Priority.START))
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
        logging.info(f"Wrote {CACHE_PATH}{frame_no}.h264")
        os.remove(f"{CACHE_PATH}{frame_no}.h264")
        frame_no += 1
    logging.info("Reader Finished")


def set_up_dirs(cache_path: str):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            f"{cache_path} must not already exist as a non directory"
        )


usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"

if __name__ == "__main__":
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
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(log_path),
                        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
                        level=logging.INFO,
                        datefmt="%Y-%m-%d %H:%M:%S")

    server_ip, server_port = args.host, int(args.port)
    set_up_dirs(CACHE_PATH)




    UDP = True  # TODO SWITCH TO CLA
    logging.info(f"Creating socket for {args.host} port {args.port}")
    client_socket = socket(AF_INET, SOCK_DGRAM if UDP else SOCK_STREAM)

    def clean_up(sig, frame):
        shutil.rmtree(CACHE_PATH)
        client_socket.sendto(b"END", (server_ip, server_port))
        client_socket.close()
        sys.exit(0)


    signal.signal(signal.SIGINT, clean_up)
    # if not UDP:
    #     client_socket.connect((server_ip, int(server_port)))
    logging.info("Socket Connected!")
    client_socket.sendto(b"Send me files!", (server_ip, server_port))
    Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)  # create directory if it does not exist
    meta_data_msg = client_socket.recv(1024)
    meta_data: Metadata = Metadata.unpack(meta_data_msg)
    logging.info(f"Received metadata at {int(time.time() * 1000)}ms")
    logging.info(f"MSG = {meta_data_msg}")
    logging.info(f"Metadata = {meta_data.to_dict()}")
    writer_thread = threading.Thread(target=writer, args=(client_socket, meta_data, (server_ip, server_port)))
    reader_thread = threading.Thread(target=reader, args=(meta_data,))
    writer_thread.start()
    reader_thread.start()

    writer_thread.join()
    reader_thread.join()
    client_socket.sendto(b"END", (server_ip, server_port))
    client_socket.close()

    logging.info("Finished")
