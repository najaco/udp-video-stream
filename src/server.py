import sys
import threading
from socket import *


def server_handler(conSocket, ad):
    frame_no = 0
    total_frames = 457
    while True:
        frame_no += 1
        frame = open("../assets/snow_{}.jpeg".format(frame_no), "rb")
        msg = frame.read()
        conSocket.send(msg)
        print("Sent Frame #: {}".format(frame_no))
        frame_no = frame_no % total_frames
    conSocket.close()


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
