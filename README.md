# UDP Video Stream
[![Build Status](https://travis-ci.com/nathancohen4299/udp-video-stream.svg?branch=dev)](https://travis-ci.com/nathancohen4299/udp-video-stream)

## Summary
UDP Video Stream is a server client streaming application written in python which streams video using UDP except for packets deemed important, in which they are sent over UDP with elements of RDT. 


## Usage
### Server
```
python3 src/server.py <port_no> <path_to_file>
```

### Client
```
python3 src/client.py <ip_address> <port_no> | vlc --demux h264 -
```

## Dependencies
#### Dependences for the **server**:
* [FFmpeg](https://www.ffmpeg.org/)
#### Dependencies for the **client**:
* [VLC](https://www.videolan.org/vlc/index.html)