import argparse
import configparser
import logging
import os
import shutil
import signal
import sys
import threading
import time
from pathlib import Path
from socket import *
from typing import List, Tuple

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
FPS: int = int(config["DEFAULT"]["FPS"])
CACHE_PATH: str = config["SERVER"]["CachePath"]
LOG_PATH: str = config["SERVER"]["LogPath"]
RETR_TIME = int(config["SERVER"]["RetransmissionTime"])
RETR_INTERVAL = float(config["SERVER"]["RetransmissionInterval"])

sessions = {}


def cl_ffmpeg(file_path: str, cache_path: str, fps: int):
    if not os.path.exists(cache_path):
        os.mkdir(cache_path)
    elif not os.path.isdir(cache_path):
        raise Exception(
            f"{cache_path} must not already exist as a non directory"
        )
    cmd = f"ffmpeg -i {file_path} -r {fps} -f image2 -c:v copy -bsf h264_mp4toannexb {cache_path}%d.h264"
    os.system(cmd)


def clean_up(sig, frame):
    shutil.rmtree(CACHE_PATH)
    sys.exit(0)


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


def server_handler(con_socket, addr_ip_port: Tuple[str, int], path_to_frames, starting_frame, total_frames):
    logging.info("Handler Started")
    frame_no = starting_frame
    meta_data = Metadata(file_name=path_to_frames, number_of_frames=total_frames)
    frames = {}
    critical_frame_acks = {}
    frame_retr_times: DeltaList[int] = DeltaList()

    def reader() -> None:
        logging.info("Reader Started")
        while True:
            if len(sessions[addr_ip_port]) <= 0:
                time.sleep(0.2)
                continue
            else:
                msg_from = sessions[addr_ip_port].pop()
                logging.info(f"Server Handler: Message from {addr_ip_port}")
            if len(msg_from) == 0:
                break
            a: Ack = Ack.unpack(msg_from)
            critical_frame_acks[a.frame_no] = True
            # remove frame from dlist here
            if frame_retr_times.contains(a.frame_no):
                frame_retr_times.remove(a.frame_no)
            logging.info(f"ACK {a.frame_no}")
        logging.info("Reader Finished")

    def retransmitter(reader_thread) -> None:
        logging.info("Retransmitter Started")
        while reader_thread.is_alive():
            # logging.info(f"Delta list = {frame_retr_times.list_as_str()}")
            frame_retr_times.decrement_key()
            ready_frames: List[int] = frame_retr_times.remove_all_ready()
            for i in ready_frames:
                logging.info(f"Retransmitting frame {i}")
                if i in critical_frame_acks and critical_frame_acks[i] is False:
                    frame_retr_times.insert(
                        k=RETR_TIME, e=i
                    )  # re insert frame to delta list
                    n_packs = 0
                    for packet in create_packets(frames[i]):
                        con_socket.sendto(packet.pack(), addr)  # HERE
                        n_packs += 1
                logging.info(f"Retransmitted frame {i} with {n_packs} packets")

            time.sleep(.001)
        logging.info("Retransmitter Finished")

    reader_thread = threading.Thread(target=reader, args=())
    retransmitter_thread = threading.Thread(target=retransmitter, args=(reader_thread,))
    reader_thread.start()
    retransmitter_thread.start()

    con_socket.sendto(meta_data.pack(), addr)
    logging.info(f"Priority Threshold is {int(PRIORITY_THRESHOLD)}")
    while frame_no < total_frames:  # 1 for now, change to frames later
        frame_no += 1
        f = open(f"{path_to_frames}{frame_no}.h264", "rb")
        frame = Frame(f.read(), frame_no)
        frames[frame_no] = frame
        logging.info(f"Frame {frame_no} has priority {frame.priority}")
        if frame.priority >= int(PRIORITY_THRESHOLD) or frame.priority == Frame.Priority.START:
            logging.info(f"Inserting {frame_no} into frame_retr_times")
            critical_frame_acks[frame_no] = False
            frame_retr_times.insert(k=RETR_TIME, e=frame_no)
        n_packets = 0
        for p in create_packets(frame):
            con_socket.sendto(p.pack(), addr)
            n_packets += 1
        logging.info(f"Frame {frame_no} had {n_packets} packets")
        logging.info(f"Frame {frame_no} sent at {int(time.time() * 1000)}ms")
        time.sleep(1 / FPS)  # sleep to simulate live streaming
    reader_thread.join()
    retransmitter_thread.join()
    con_socket.close()
    con_socket.sendto(b"END", addr)
    logging.info("Handler Finished")


usage = "usage: python " + sys.argv[0] + " [portno] [file]"

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
        "-f",
        "--file-to-send",
        type=str,
        required=True,
        help="load the TLS private key from the specified file",
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
    server_port = args.port
    file_path = args.file_to_send

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(log_path),
                        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
                        level=logging.INFO,
                        datefmt="%Y-%m-%d %H:%M:%S")

    cl_ffmpeg(file_path, CACHE_PATH, FPS)

    UDP = True  # TODO: Switch to CLA
    logging.info(f"Creating socket on {args.host} port {args.port}")
    server_socket = socket(AF_INET, SOCK_DGRAM if UDP else SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server_socket.bind(("", int(server_port)))
    logging.info(f"Socket Bound")
    if not UDP:
        server_socket.listen(8)

    number_of_frames = len(os.listdir(CACHE_PATH))
    logging.info("Running...")

    while True:
        msg, addr = server_socket.recvfrom(1024) if UDP else server_socket.accept()
        logging.info(f"Received {msg} from {addr} at {time.time()}ms")

        # If session is not already established, create one
        if addr not in sessions:
            sessions[addr] = []
            threading.Thread(
                target=server_handler,
                args=(server_socket, addr, CACHE_PATH, 0, number_of_frames),
            ).start()
        elif msg == b"END":
            logging.info(f"Detected END from {addr}. Reseting session")
            sessions.pop(addr)
        else:
            sessions[addr].append(msg)
    server_socket.close()
