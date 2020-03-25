import logging
import os
import struct
import sys
import threading
import time
from objs.frame import Frame
from objs.packet import Packet
from os import path
from socket import *
from typing import List

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4

PATH_TO_CACHE = "./temp/"

usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"


def main():
    writer_thread = threading.Thread(target=writer, args=(sys.argv[1], sys.argv[2]))
    reader_thread = threading.Thread(target=reader, args=())
    writer_thread.start()
    reader_thread.start()

    writer_thread.join()
    reader_thread.join()


def writer(server_ip, server_port):
    logging.info("Writer started")
    client_socket = socket(AF_INET, SOCK_STREAM)
    client_socket.connect((server_ip, int(server_port)))
    frames = {}
    while True:
        msg_from = client_socket.recv(1024)
        if len(msg_from) == 0:
            break
        t = struct.unpack("!IIII{}s".format(len(msg_from) - 4 * 4), msg_from)
        p: Packet = Packet(t[0], t[1], t[2], t[3], t[4])  # Takes all except for the padding

        # check if frame # of packet is in frames here

        if p.frame_no not in frames:
            frames[p.frame_no] = Frame(p.total_seq_no)
        try:
            frames[p.frame_no].emplace(p.seq_no, p.data)
        except Exception:
            print("Error with frame no {}".format(p.frame_no))
        # check if frame is filled
        if frames[p.frame_no].is_complete():
            frame_to_save = open("./temp/{}.h264".format(p.frame_no), "wb+")
            frame_to_save.write(frames[p.frame_no].get_data_as_bytes())

            frame_to_save.close()
            del frames[p.frame_no]  # delete frame now that it has been saved

    client_socket.close()


def reader():
    logging.info("Reader started")
    frame_no = 1
    while True:
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


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        exit(1)
    logging.basicConfig(filename='client.log', level=logging.INFO)

    main()
