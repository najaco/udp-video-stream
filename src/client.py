import sys
from socket import *

usage = "usage: python " + sys.argv[0] + " [serverIP] " + " [serverPort]"
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(usage)
        exit(1)

serverIP = sys.argv[1]
serverPort = sys.argv[2]

clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect((serverIP, int(serverPort)))
frame_no = 0
while True:
    frame_no += 1
    msg_from = clientSocket.recv(1024)
    print("Received frame no {}".format(frame_no))
    frame_to_save = open("./temp/frame_{}.jpeg".format(frame_no), "wb+")
    frame_to_save.write(msg_from)
    frame_to_save.close()
clientSocket.close()