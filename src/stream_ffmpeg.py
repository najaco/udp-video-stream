import ffmpeg

if __name__ == "__main__":
    stream = ffmpeg.input('./assets/snow.mp4')
    stream = ffmpeg.output(stream, 'output.mp4')
    stream.run(stream)
