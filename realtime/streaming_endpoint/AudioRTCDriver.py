import asyncio
import fractions
import time
from av import AudioFrame
from aiortc import MediaStreamTrack
from realtime.data import AudioData
from av import AudioResampler
import logging


class AudioRTCDriver(MediaStreamTrack):
    kind = "audio"

    def __init__(
        self,
        audio_input_q,
        audio_output_q,
        output_audio_sample_rate=48000,
        output_audio_layout="stereo",
        output_audio_format="s16",
    ):
        super().__init__()
        self.audio_input_q = audio_input_q
        self.audio_output_q = audio_output_q
        self.audio_data_q = asyncio.Queue()
        self.audio_samples = 0
        self._start = None
        self._track = None
        self.output_audio_sample_rate = output_audio_sample_rate
        self.output_audio_layout = output_audio_layout
        self.output_audio_format = output_audio_format
        self.output_audio_time_base = fractions.Fraction(1, self.output_audio_sample_rate)
        self.output_audio_chunk_size_seconds = 0.020
        self.output_audio_resampler = AudioResampler(
            format=self.output_audio_format,
            layout=self.output_audio_layout,
            rate=self.output_audio_sample_rate,
            frame_size=int(self.output_audio_sample_rate * self.output_audio_chunk_size_seconds),
        )

    async def recv(self):
        frame = await self.audio_data_q.get()
        print("audio frame", frame.samples, frame.sample_rate)
        data_time = frame.samples / frame.sample_rate
        if self._start is None:
            self._start = time.time() + data_time
        else:
            wait = self._start - time.time() - 0.005
            if wait > 0:
                await asyncio.sleep(wait)
            self._start = time.time() + data_time
        return frame

    async def run_input(self):
        try:
            if not self.audio_input_q:
                return
            while not self._track:
                await asyncio.sleep(0.2)
            while True:
                frame = await self._track.recv()
                await self.audio_input_q.put(frame)
        except Exception as e:
            logging.error("Error in audio_frame_callback: ", e)
            raise asyncio.CancelledError

    async def run_output(self):
        try:
            while True:
                audio_data: AudioData = await self.audio_output_q.get()
                self.audio_samples = max(self.audio_samples, audio_data.get_pts())
                for nframe in self.output_audio_resampler.resample(audio_data.get_frame()):
                    # fix timestamps
                    nframe.pts = self.audio_samples
                    nframe.time_base = self.output_audio_time_base
                    self.audio_samples += nframe.samples
                    self.audio_data_q.put_nowait(nframe)
        except Exception as e:
            logging.error("Error in audio_frame_callback: ", e)
            raise asyncio.CancelledError

    async def run(self):
        await asyncio.gather(self.run_input(), self.run_output())

    def add_track(self, track):
        self._track = track
