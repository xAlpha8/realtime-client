import asyncio
import base64
import json
import logging
from typing import Any, Dict, Tuple

import websockets

import realtime as rt
from realtime.data import AudioData, ImageData
from realtime.streams import AudioStream, VideoStream

# Set up basic logging configuration
logging.basicConfig(level=logging.INFO)


class DeepreelPlugin:
    """
    A plugin for processing audio input and generating video output using a WebSocket connection.
    """

    def __init__(self, websocket_url: str):
        """
        Initialize the DeepreelPlugin.

        Args:
            websocket_url (str): The URL of the WebSocket server to connect to.
        """
        self.websocket_url: str = websocket_url
        self.audio_samples: int = 0
        self.audio_input_stream: AudioStream
        self.image_output_stream: VideoStream
        self.audio_output_stream: AudioStream
        self._ws: websockets.WebSocketClientProtocol
        self._audio_library: Dict[float, AudioData] = {}

    def run(self, audio_input_stream: AudioStream) -> Tuple[VideoStream, AudioStream]:
        """
        Set up the plugin and start processing audio input.

        Args:
            audio_input_stream (AudioStream): The input audio stream to process.

        Returns:
            Tuple[VideoStream, AudioStream]: The output video and audio streams.
        """
        self.audio_input_stream = audio_input_stream
        self.image_output_stream = VideoStream()
        self.audio_output_stream = AudioStream()
        asyncio.create_task(self.task())
        return self.image_output_stream, self.audio_output_stream

    async def task(self):
        """
        The main task for processing audio input and generating video output.
        """
        self._ws = await websockets.connect(self.websocket_url)

        async def send_task():
            """
            Continuously send audio data to the WebSocket server.
            """
            while True:
                audio_data: AudioData = await self.audio_input_stream.get()
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
            """
            Continuously receive and process video data from the WebSocket server.
            """
            start_time = 0.0
            while True:
                msg = await self._ws.recv()

                response_data: Dict[str, Any] = json.loads(msg)
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
                        audio_data.relative_start_time = start_time
                        self.audio_output_stream.put_nowait(audio_data)

                    start_time += image["duration"]

        # Run send_task and recv_task concurrently
        await asyncio.gather(send_task(), recv_task())


@rt.App()
class DeepReelBot:
    """
    A bot that processes audio input, generates responses, and produces video output.
    """

    async def setup(self):
        """
        Set up the bot. Currently empty, but can be used for initialization if needed.
        """
        pass

    @rt.streaming_endpoint()
    async def run(
        self, audio_input_stream: rt.AudioStream, message_stream: rt.TextStream
    ) -> Tuple[rt.VideoStream, rt.AudioStream]:
        """
        The main processing pipeline for the bot.

        Args:
            audio_input_stream (rt.AudioStream): The input audio stream.
            message_stream (rt.TextStream): The input text message stream.

        Returns:
            Tuple[rt.VideoStream, rt.AudioStream]: The output video and audio streams.
        """
        # Initialize processing nodes
        deepgram_node = rt.DeepgramSTT(sample_rate=audio_input_stream.sample_rate)
        llm_node = rt.GroqLLM(
            system_prompt="You are a virtual assistant. Keep the response short and concise.",
            temperature=0.9,
            stream=False,
        )
        token_aggregator_node = rt.TokenAggregator()
        tts_node = rt.CartesiaTTS()
        deepreel_node = DeepreelPlugin(websocket_url="ws://localhost:8765/ws")

        # Set up the processing pipeline
        deepgram_stream = deepgram_node.run(audio_input_stream)
        message_stream = rt.map(message_stream, lambda x: json.loads(x).get("content"))
        deepgram_stream = rt.merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = llm_node.run(deepgram_stream)
        token_aggregator_stream = token_aggregator_node.run(llm_token_stream)

        tts_stream = tts_node.run(token_aggregator_stream)
        video_stream, audio_stream = deepreel_node.run(tts_stream)

        return video_stream, audio_stream

    async def teardown(self):
        """
        Clean up resources when the bot is shutting down. Currently empty, but can be implemented if needed.
        """
        pass


if __name__ == "__main__":
    bot = DeepReelBot()
    bot.start()
