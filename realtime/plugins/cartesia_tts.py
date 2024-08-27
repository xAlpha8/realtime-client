import asyncio
import base64
import json
import logging
import os
import time
import uuid
from urllib.parse import urlencode

import websockets

from realtime.data import AudioData
from realtime.plugins.base_plugin import Plugin
from realtime.streams import ByteStream, TextStream


class CartesiaTTS(Plugin):
    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
        model: str = "sonic-english",
        output_encoding: str = "pcm_s16le",
        output_sample_rate: int = 16000,
        stream: bool = True,
        base_url: str = "wss://api.cartesia.ai/tts/websocket",
        cartesia_version: str = "2024-06-10",
    ):
        super().__init__()

        self._generating = False

        self.api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        if self.api_key is None:
            raise ValueError("Cartesia API key is required")
        self.voice_id = voice_id
        self.model = model
        self.output_encoding = output_encoding
        self.output_sample_rate = output_sample_rate
        self.output_queue = ByteStream()
        self.stream = stream
        self.base_url = base_url
        self.cartesia_version = cartesia_version

    def run(self, input_queue: TextStream) -> ByteStream:
        self.input_queue = input_queue
        self._task = asyncio.create_task(self.synthesize_speech())
        return self.output_queue

    async def synthesize_speech(self):
        query_params = {
            "cartesia_version": self.cartesia_version,
            "api_key": self.api_key,
        }
        try:
            self._ws = await websockets.connect(f"{self.base_url}?{urlencode(query_params)}")
        except Exception as e:
            logging.error("Error connecting to Cartesia TTS: %s", e)
            raise asyncio.CancelledError()

        async def send_text():
            try:
                while True:
                    text_chunk = await self.input_queue.get()
                    if text_chunk is None or text_chunk == "":
                        continue
                    start_time = time.time()
                    logging.info("Generating TTS %s", text_chunk)
                    payload = {
                        "voice": {"mode": "id", "id": self.voice_id},
                        "output_format": {
                            "encoding": self.output_encoding,
                            "sample_rate": self.output_sample_rate,
                            "container": "raw",
                        },
                        "transcript": text_chunk,
                        "model_id": self.model,
                        "context_id": str(uuid.uuid4()),
                        "continue": True,
                    }
                    self._generating = True
                    await self._ws.send(json.dumps(payload))
                    logging.info("Cartesia TTS TTFB: %s", time.time() - start_time)
            except Exception as e:
                logging.error("Error sending text to Cartesia TTS: %s", e)
                await self.output_queue.put(None)
                self._generating = False
                raise asyncio.CancelledError()

        async def receive_audio():
            try:
                while True:
                    response = await self._ws.recv()
                    response = json.loads(response)
                    if response["type"] == "chunk":
                        audio_bytes = base64.b64decode(response["data"])
                        await self.output_queue.put(
                            AudioData(
                                audio_bytes,
                                sample_rate=self.output_sample_rate,
                            )
                        )
                    if response["done"]:
                        await self.output_queue.put(None)
                        self._generating = False
            except Exception as e:
                logging.error("Error receiving audio from Cartesia TTS: %s", e)
                await self.output_queue.put(None)
                self._generating = False
                raise asyncio.CancelledError()

        try:
            await asyncio.gather(send_text(), receive_audio())
        except asyncio.CancelledError:
            logging.info("TTS cancelled")
            self._generating = False
            self._task.cancel()

    async def close(self):
        await self.session.close()
        self._task.cancel()

    async def _interrupt(self):
        while True:
            user_speaking = await self.interrupt_queue.get()
            if self._generating and user_speaking:
                self._task.cancel()
                while not self.output_queue.empty():
                    self.output_queue.get_nowait()
                logging.info("Done cancelling TTS")
                self._generating = False
                self._task = asyncio.create_task(self.synthesize_speech())

    async def set_interrupt(self, interrupt_queue: asyncio.Queue):
        self.interrupt_queue = interrupt_queue
        self._interrupt_task = asyncio.create_task(self._interrupt())
