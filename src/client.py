import logging
import os
import struct
import sys
import threading
import time

from objs import Frame
from objs.frame_builder import FrameBuilder
from objs.packet import Packet
from objs.metadata import Metadata
from objs.ack import Ack
from os import path
from socket import *
from typing import List

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4

PATH_TO_CACHE = "./temp/"
PRIORITY_THRESHOLD = Frame.Priority.IMPORTANT


def writer(client_socket, meta_data: Metadata):
    logging.info("Writer Started")
    logging.info("Receiving {} with {} frames".format(meta_data.file_name, meta_data.number_of_frames))

    frames = {}
    completed_frames = 0
    while completed_frames < meta_data.number_of_frames:
        msg_from = client_socket.recv(1024)
        if len(msg_from) == 0:
            break
        p: Packet = Packet.unpack(msg_from)

        # check if frame # of packet is in frames here

        if p.frame_no not in frames:
            frames[p.frame_no] = FrameBuilder(p.total_seq_no)
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
    while frame_no < meta_data.number_of_frames:
        logging.info("Waiting for {}{}.h264 exists".format(PATH_TO_CACHE, frame_no))
        while not path.exists("{}{}.h264".format(PATH_TO_CACHE, frame_no)):
            time.sleep(1)  # force context switch
        logging.info("Starting {}{}.h264".format(PATH_TO_CACHE, frame_no))

        with open("{}{}.h264".format(PATH_TO_CACHE, frame_no), "rb") as f:
            with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                stdout.write(f.read())
                stdout.flush()
        logging.info("Finished {}{}.h264".format(PATH_TO_CACHE, frame_no))
        logging.info("Deleting {}{}.h264".format(PATH_TO_CACHE, frame_no))
        os.remove("{}{}.h264".format(PATH_TO_CACHE, frame_no))
        frame_no += 1
    logging.info("Reader Finished")


usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"


def main():
    server_ip, server_port = sys.argv[1], sys.argv[2]
    client_socket = socket(AF_INET, SOCK_STREAM)
    client_socket.connect((server_ip, int(server_port)))
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
    logging.basicConfig(filename='client.log', level=logging.INFO)
    main()
