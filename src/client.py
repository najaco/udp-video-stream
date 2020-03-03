import struct
import sys
import os
from objs.frame import Frame
from objs.packet import Packet
from socket import *
from typing import List

MAX_PKT_SIZE = 1024
MAX_DATA_SIZE = MAX_PKT_SIZE - 4 * 4

usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        exit(1)

    serverIP = sys.argv[1]
    serverPort = sys.argv[2]

    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverIP, int(serverPort)))
    frames = {}
    buffer = ""
    last_frame_no = 0
    while True:
        msg_from = clientSocket.recv(1024)
        if len(msg_from) == 0:
            break
        t = struct.unpack("!IIII{}s".format(len(msg_from) - 4 * 4), msg_from)
        p: Packet = Packet(t[0], t[1], t[2], t[3], t[4]) # Takes all except for the padding
        # check if frame # of packet is in frames here
        # frame_to_save.write(t[4])
        if p.frame_no not in frames:
            frames[p.frame_no] = Frame(p.total_seq_no)
        try:
            frames[p.frame_no].emplace(p.seq_no, p.data)
        except Exception:
            print("Error with frame no {}".format(p.frame_no))

        # check if frame is filled
        if frames[p.frame_no].is_complete():
            #frame_to_save = open("./temp/{}.h264".format(p.frame_no), "wb+")
            #frame_to_save.write(frames[p.frame_no].get_data_as_bytes())
            if p.frame_no > last_frame_no:
                with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
                    stdout.write(frames[p.frame_no].get_data_as_bytes())
                    stdout.flush()
                last_frame_no = p.frame_no
            #frame_to_save.close()
            #lprint("Frame {} written".format(p.frame_no))
            #print(frames[p.frame_no].get_data_as_bytes())
            del frames[p.frame_no] # delete frame now that it has been saved

    clientSocket.close()
