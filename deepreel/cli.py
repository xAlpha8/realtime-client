import asyncio
import logging
import os
import random
import time
from typing import Tuple

logging.basicConfig(level=logging.INFO)

import av
from aiortc.contrib.media import MediaPlayer

import realtime
from realtime.streams import AudioStream, Stream, VideoStream


@realtime.App()
class ReplayBot:
    async def setup(self):
        pass

    @realtime.streaming_endpoint()
    async def run(self, audio_input: AudioStream) -> Tuple[Stream, ...]:
        folder = os.path.dirname(os.path.abspath(__file__))
        player = MediaPlayer(f"{folder}/videoplayback.mp4")
        container = av.open(f"{folder}/videoplayback.mp4", mode="r")
        video_time_base = container.streams.video[0].time_base
        framerate = container.streams.video[0].average_rate
        print(video_time_base, framerate)
        audio_stream = AudioStream()
        video_stream = VideoStream()

        async def sync(video_stream: VideoStream, audio_stream: AudioStream):
            await audio_input.get()
            samples = 0
            video_frame = next(container.decode(container.streams.video[0]))
            start_time = time.time()
            while True:
                audio_frame = await player.audio.recv()
                time_since_start = audio_frame.time_base * audio_frame.pts
                offset = round(time_since_start / video_time_base)
                while video_frame.pts < offset:
                    video_frame = next(container.decode(container.streams.video[0]))
                video_frame.pts += 2 * 30000
                audio_frame.pts += 48000
                print(
                    video_time_base,
                    audio_frame.time_base,
                    audio_frame.pts,
                    offset,
                    video_frame,
                )
                samples += random.randint(1, 10)
                await audio_stream.put(audio_frame)
                await video_stream.put(video_frame)
                audio_frame.pts -= 48000
                video_frame.pts -= 2 * 30000

        asyncio.create_task(sync(video_stream, audio_stream))
        return video_stream, audio_stream

    async def teardown(self):
        pass


if __name__ == "__main__":
    asyncio.run(ReplayBot().run())
