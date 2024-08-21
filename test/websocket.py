import asyncio
import base64
import io
import json
import logging
import time
import wave

import av
import numpy as np
from fastapi import WebSocket
from realtime.server import RealtimeServer
from realtime.streams import AudioStream, TextStream
from realtime.plugins.deepgram_stt import DeepgramSTT
from realtime.plugins.fireworks_llm import FireworksLLM
from realtime.plugins.azure_tts import AzureTTS
import realtime
from realtime.ops.merge import merge
from realtime.ops.map import map

logging.basicConfig(level=logging.INFO)

class WebsocketInputStream:
    """
    Handles incoming WebSocket messages and streams audio and text data.

    Attributes:
        ws (WebSocket): The WebSocket connection.
        audio_output_stream (AudioStream): Stream for audio data.
        message_stream (TextStream): Stream for text messages.
    """
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.audio_output_stream = AudioStream()
        self.message_stream = TextStream()

    async def run(self):
        """
        Starts the task to process incoming WebSocket messages.

        Returns:
            Tuple[AudioStream, TextStream]: A tuple containing the audio and message streams.
        """
        self._task = asyncio.create_task(self.task())
        return self.audio_output_stream, self.message_stream

    async def task(self):
        """
        Continuously receives data from the WebSocket and processes it based on its type.
        """
        audio_data = b""
        while True:
            data = await self.ws.receive_json()
            if data.get("type") == "message":
                await self.message_stream.put(data.get("data"))
            elif data.get("type") == "audio":
                audio_bytes = base64.b64decode(data.get("data"))
                audio_data += audio_bytes

                if len(audio_data) < 2:
                    continue
                if len(audio_data) % 2 != 0:
                    array = np.frombuffer(audio_data[:-1], dtype=np.int16).reshape(1, -1)
                    audio_data = audio_data[-1:]
                else:
                    array = np.frombuffer(audio_data, dtype=np.int16).reshape(1, -1)
                    audio_data = b""

                frame = av.AudioFrame.from_ndarray(array, format="s16", layout="mono")
                frame.sample_rate = 8000
                await self.audio_output_stream.put(frame)

class WebsocketOutputStream:
    """
    Handles outgoing WebSocket messages by streaming audio and text data.

    Attributes:
        ws (WebSocket): The WebSocket connection.
    """
    def __init__(self, ws: WebSocket):
        self.ws = ws

    async def run(self, audio_stream: AudioStream, message_stream: TextStream):
        """
        Starts tasks to process and send audio and text streams.

        Args:
            audio_stream (AudioStream): The audio stream to send.
            message_stream (TextStream): The text stream to send.
        """
        await asyncio.gather(self.task(audio_stream), self.task(message_stream))

    async def task(self, input_stream):
        """
        Sends data from the input stream over the WebSocket.

        Args:
            input_stream (Stream): The stream from which to send data.
        """
        while True:
            data = await input_stream.get()
            if data is None:
                json_data = {
                    "type": "audio_end",
                    "timestamp": time.time()
                }
                await self.ws.send_json(json_data)
            elif isinstance(data, bytes):
                output_bytes_io = io.BytesIO()
                in_memory_wav = wave.open(output_bytes_io, "wb")
                in_memory_wav.setnchannels(1)
                in_memory_wav.setsampwidth(2)
                in_memory_wav.setframerate(16000)
                in_memory_wav.writeframes(data)
                output_bytes_io.seek(0)
                data = output_bytes_io.read()
                json_data = {
                    "type": "audio",
                    "data": base64.b64encode(data).decode(),
                    "timestamp": time.time()
                }
                await self.ws.send_json(json_data)
            elif isinstance(data, str):
                json_data = {
                    "type": "message",
                    "data": data,
                    "timestamp": time.time()
                }
                await self.ws.send_json(json_data)
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

@realtime.App()
class ReplayBot:
    """
    A bot that uses WebSocket to interact with clients, processing audio and text data.

    Methods:
        setup(): Prepares any necessary configurations.
        run(ws: WebSocket): Handles the WebSocket connection and processes data.
        teardown(): Cleans up any resources or configurations.
    """
    async def setup(self):
        pass

    @realtime.websocket()
    async def run(ws: WebSocket):
        await ws.accept()

        audio_metadata = await ws.receive_json()
        audio_input_stream, message_stream = await WebsocketInputStream(ws).run()

        deepgram_node = DeepgramSTT(sample_rate=audio_metadata.get("sampleRate", 48000))
        llm_node = FireworksLLM(
            system_prompt="You are a virtual girlfriend.\
            You will always reply with a JSON object.\
            Each message has a text, facialExpression, and animation property.\
            The text property is a short response to the user (no emoji).\
            The different facial expressions are: smile, sad, angry, surprised, funnyFace, and default.\
            The different animations are: Talking_0, Talking_1, Talking_2, Crying, Laughing, Rumba, Idle, Terrified, and Angry.",
            temperature=0.9,
            response_format={"type": "json_object"},
            stream=False,
            model="accounts/fireworks/models/llama-v3-70b-instruct",
        )
        tts_node = AzureTTS(stream=False)

        deepgram_stream = await deepgram_node.run(audio_input_stream)
        deepgram_stream = merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = await llm_node.run(deepgram_stream)

        json_text_stream = map(
            await llm_token_stream.clone(), lambda x: json.loads(x).get("text")
        )

        tts_stream, viseme_stream = await tts_node.run(json_text_stream)

        llm_with_viseme_stream = merge([llm_token_stream, viseme_stream])

        await WebsocketOutputStream(ws).run(tts_stream, llm_with_viseme_stream)

    async def teardown(self):
        pass

if __name__ == "__main__":
    v = ReplayBot()
    asyncio.run(RealtimeServer().start())