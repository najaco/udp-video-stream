# Links
* https://www.ffmpeg.org/
* https://tldr.ostera.io/ffmpeg
* https://en.wikipedia.org/wiki/YCbCr
* https://en.wikipedia.org/wiki/Video_coding_format
* https://en.wikipedia.org/wiki/Video_codec
* https://trac.ffmpeg.org/wiki/Encode/H.264

# Commands
* `vlc --demux=rawvideo --rawvid-fps=25 --ra=wvid-width=640 --rawvid-height=480 --rawvid-chroma=RV24 - --sout "#display"`
    * Pipe output of video reader inot this?
* cat road480p/{1..626}.h264 | vlc --demux h264 -
