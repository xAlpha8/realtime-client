import asyncio
import logging

from aiortc import MediaStreamTrack
from aiortc.contrib.media import MediaRecorder
from av import AudioFrame

import realtime as rt

logging.basicConfig(level=logging.INFO)

"""
Wrapping your class with @realtime.App() will tell the realtime server which functions to run.
"""

class AudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, input_queue):
        super().__init__()
        self.input_queue = input_queue

    async def recv(self):
        return await self.input_queue.get()

class RealtimeRecord:
    def __init__(self, path):
        self.media_recorder = MediaRecorder(path)
        pass

    async def _start_recording(self):
        await self.media_recorder.start()

    def run(self, input_queue: asyncio.Queue) -> AudioFrame:
        audio_track = AudioTrack(input_queue)
        self.media_recorder.addTrack(audio_track)
        self._task = asyncio.create_task(self._start_recording())

    async def close(self):
        await self.media_recorder.stop()
        if self._task:
            self._task.cancel()


@rt.App()
class RecordAudioBot:
    async def setup(self):
        self.rr = RealtimeRecord('./file.wav')

    @rt.streaming_endpoint()
    async def run(self, audio_input_queue: rt.AudioStream):
        recordable_audio = audio_input_queue.clone()
        self.rr.run(recordable_audio)

        return (audio_input_queue, None, None)

    async def teardown(self):
        await self.rr.close()


if __name__ == "__main__":
    RecordAudioBot().start()
