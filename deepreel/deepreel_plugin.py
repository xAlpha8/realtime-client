import asyncio
import base64
import fractions
import io
import json
import time
import websockets
from av import AudioResampler

from realtime.data import AudioData, ImageData
from realtime.streams import AudioStream, VideoStream
from realtime.utils.clock import Clock


class DeepreelPlugin:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.audio_samples = 0
        self.output_audio_sample_rate = 48000
        self.output_audio_time_base = fractions.Fraction(1, self.output_audio_sample_rate)
        self.output_audio_resampler = AudioResampler(
            format="s16",
            layout="stereo",
            rate=self.output_audio_sample_rate,
            frame_size=int(self.output_audio_sample_rate * 0.020),
        )

    async def run(self, audio_input_stream: AudioStream):
        self.audio_input_stream = audio_input_stream
        self.image_output_stream = VideoStream()
        self.audio_output_stream = AudioStream()
        asyncio.create_task(self.task())
        return self.image_output_stream, self.audio_output_stream

    async def task(self):
        self._ws = await websockets.connect(self.websocket_url)
        self._audio_library = {}

        async def send_task():
            while True:
                audio_data = await self.audio_input_stream.get()
                if audio_data is None:
                    continue
                audio_duration = audio_data.get_duration_seconds()
                audio_json = {
                    "audio_data": audio_data.get_base64(),
                    "start_seconds": audio_data.get_start_seconds(),
                    "end_seconds": audio_data.get_start_seconds() + audio_duration,
                    "audio_format": "pcm_16000",
                }
                await self._ws.send(json.dumps(audio_json))
                self._audio_library[audio_json["start_seconds"]] = audio_data

        async def recv_task():
            start_time = Clock.get_seconds_since_start()
            while True:
                msg = await self._ws.recv()

                response_data = json.loads(msg)
                images = response_data.get("image_data", [])
                for image in images:
                    # Decode the base64 string to bytes
                    image_bytes = base64.b64decode(image["image"])
                    image_data = ImageData(
                        data=image_bytes,
                        format="jpeg",
                        frame_rate=30,
                        relative_start_time=start_time,
                    )
                    image_frame = image_data.get_frame()
                    print(image_frame)
                    self.image_output_stream.put_nowait(image_frame)

                    if image["start_seconds"] in self._audio_library:
                        audio_data: AudioData = self._audio_library.pop(image["start_seconds"])
                        audio_data.relative_start_time = start_time
                        audio_frame = audio_data.get_frame()
                        self.audio_samples = audio_frame.pts
                        print(audio_frame)
                        for nframe in self.output_audio_resampler.resample(audio_frame):
                            # fix timestamps
                            nframe.pts = self.audio_samples
                            nframe.time_base = self.output_audio_time_base
                            self.audio_samples += nframe.samples
                            print(nframe)
                            self.audio_output_stream.put_nowait(nframe)

                    start_time += image["duration"]

        await asyncio.gather(send_task(), recv_task())

    def convert_bytes_to_frames(self, audio_data: AudioData):
        audio_frames = []
        for nframe in self.output_audio_resampler.resample(audio_data.get_frame()):
            # fix timestamps
            nframe.pts = self.audio_samples
            nframe.time_base = self.output_audio_time_base
            self.audio_samples += nframe.samples
            audio_frames.append(nframe)
        return audio_frames
