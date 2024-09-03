import asyncio
import base64
import io
import logging
import time
import wave

from fastapi import WebSocket

from realtime.data import AudioData
from realtime.streams import AudioStream, ByteStream, TextStream, VideoStream
from pydub import AudioSegment


def resample_wav_bytes(audio_data: AudioData, target_sample_rate: int) -> bytes:
    """
    Resample WAV bytes to a target sample rate.

    Args:
        wav_bytes (bytes): The input WAV file as bytes.
        target_sample_rate (int): The desired sample rate in Hz.

    Returns:
        bytes: The resampled WAV file as bytes.
    """
    wav_bytes = audio_data.get_bytes()
    if audio_data.sample_rate == target_sample_rate:
        return wav_bytes
    # Load WAV bytes into AudioSegment
    audio = AudioSegment.from_wav(io.BytesIO(wav_bytes))

    # Resample the audio
    resampled_audio = audio.set_frame_rate(target_sample_rate)

    # Export the resampled audio to bytes
    output = io.BytesIO()
    resampled_audio.export(output, format="wav")
    return output.getvalue()


class WebsocketInputStream:
    """
    Handles incoming WebSocket messages and streams audio and text data.

    Attributes:
        ws (WebSocket): The WebSocket connection.
    """

    def __init__(self, ws: WebSocket, sample_rate: int = 48000):
        self.ws = ws
        self.sample_rate = sample_rate

    async def run(self, audio_stream: AudioStream, message_stream: TextStream, video_stream: VideoStream):
        """
        Starts the task to process incoming WebSocket messages.

        Returns:
            Tuple[AudioStream, TextStream]: A tuple containing the audio and message streams.
        """
        self.audio_output_stream = audio_stream
        self.message_stream = message_stream

        # TODO: Implement video stream processing
        self.video_stream = video_stream

        audio_data = b""
        while True:
            try:
                data = await self.ws.receive_json()
                if data.get("type") == "message":
                    await self.message_stream.put(data.get("data"))
                elif data.get("type") == "audio":
                    audio_bytes = base64.b64decode(data.get("data"))
                    audio_data = AudioData(audio_bytes, sample_rate=self.sample_rate)
                    await self.audio_output_stream.put(audio_data)
            except Exception as e:
                logging.error("websocket: Exception", e)
                raise asyncio.CancelledError()


class WebsocketOutputStream:
    """
    Handles outgoing WebSocket messages by streaming audio and text data.

    Attributes:
        ws (WebSocket): The WebSocket connection.
    """

    def __init__(self, ws: WebSocket, sample_rate: int = 48000):
        self.ws = ws
        self.sample_rate = sample_rate

    async def run(
        self, audio_stream: AudioStream, message_stream: TextStream, video_stream: VideoStream, byte_stream: ByteStream
    ):
        """
        Starts tasks to process and send byte and text streams.

        Args:
            audio_stream (AudioStream): The audio stream to send.
            message_stream (TextStream): The text stream to send.
            video_stream (VideoStream): The video stream to send.
            byte_stream (ByteStream): The byte stream to send.
        """
        # TODO: Implement video stream and audio stream processing
        await asyncio.gather(self.task(byte_stream), self.task(message_stream))

    async def task(self, input_stream):
        """
        Sends data from the input stream over the WebSocket.

        Args:
            input_stream (Stream): The stream from which to send data.
        """
        while True:
            if not input_stream:
                break
            audio_data = await input_stream.get()
            if audio_data is None:
                print("Sending audio end")
                json_data = {"type": "audio_end", "timestamp": time.time()}
                await self.ws.send_json(json_data)
            elif isinstance(audio_data, AudioData):
                data = resample_wav_bytes(audio_data, self.sample_rate)
                json_data = {
                    "type": "audio",
                    "data": base64.b64encode(data).decode(),
                    "timestamp": time.time(),
                    "sample_rate": audio_data.sample_rate,
                }
                await self.ws.send_json(json_data)
            elif isinstance(audio_data, str):
                json_data = {"type": "message", "data": audio_data, "timestamp": time.time()}
                await self.ws.send_json(json_data)
            else:
                raise ValueError(f"Unsupported data type: {type(audio_data)}")
