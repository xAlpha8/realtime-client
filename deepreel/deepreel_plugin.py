import asyncio
import base64
import json

import websockets

from realtime.data import AudioData, ImageData
from realtime.streams import AudioStream, VideoStream
from realtime.utils.clock import Clock


class DeepreelPlugin:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.audio_samples = 0

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
            start_time = Clock.get_playback_time()
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
                    self.image_output_stream.put_nowait(image_data)

                    if image["start_seconds"] in self._audio_library:
                        audio_data: AudioData = self._audio_library.pop(image["start_seconds"])
                        self.audio_output_stream.put_nowait(audio_data)

                    start_time += image["duration"]

        await asyncio.gather(send_task(), recv_task())
