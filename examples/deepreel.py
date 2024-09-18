import asyncio
import base64
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Tuple

import websockets

import realtime as rt

# Set up basic logging configuration
logging.basicConfig(level=logging.INFO)
FRAME_RATE = 25


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
        self.audio_input_stream: rt.AudioStream
        self.image_output_stream: rt.VideoStream
        self.audio_output_stream: rt.AudioStream
        self._ws: websockets.WebSocketClientProtocol
        self._audio_library: List[Tuple[float, rt.AudioData]] = []
        self._ws = None
        self._loop = asyncio.get_running_loop()
        self._stop_event = threading.Event()
        self._speaking = False

    def run(self, audio_input_stream: rt.AudioStream) -> Tuple[rt.VideoStream, rt.AudioStream]:
        """
        Set up the plugin and start processing audio input.

        Args:
            audio_input_stream (AudioStream): The input audio stream to process.

        Returns:
            Tuple[VideoStream, AudioStream]: The output video and audio streams.
        """
        self.audio_input_stream = audio_input_stream
        self.image_output_stream = rt.VideoStream()
        self.audio_output_stream = rt.AudioStream()
        self._send_thread = threading.Thread(target=self.send_task)
        self._send_thread.start()
        self._recv_thread = threading.Thread(target=self.recv_task)
        self._recv_thread.start()

        return self.image_output_stream, self.audio_output_stream

    async def _connect_ws(self):
        """
        Coroutine to establish a WebSocket connection.
        """
        return await websockets.connect(self.websocket_url)

    def connect(self):
        """
        Establish a WebSocket connection using the provided URL.
        """
        try:
            # Ensure the event loop is set in the current thread
            self._ws = asyncio.run_coroutine_threadsafe(self._connect_ws(), self._loop).result()
        except Exception as e:
            logging.error(f"Error connecting to websocket: {e}")
            return

    def send_task(self):
        """
        Continuously send audio data to the WebSocket server.
        """
        try:
            send_first_interrupt = True
            while not self._stop_event.is_set():
                try:
                    audio_data: rt.AudioData = asyncio.run_coroutine_threadsafe(
                        asyncio.wait_for(self.audio_input_stream.get(), timeout=0.2), self._loop
                    ).result()
                except asyncio.TimeoutError:
                    continue
                if audio_data is None:
                    send_first_interrupt = True

                    continue
                if not self._ws:
                    self.connect()
                if isinstance(audio_data, rt.SessionData):
                    continue
                audio_duration = audio_data.get_duration_seconds()
                audio_bytes = audio_data.get_bytes()
                audio_start = audio_data.get_start_seconds()
                # if send_first_interrupt:
                #     audio_json = {"interrupt": True, "start_frame_idx": 0}
                #     send_first_interrupt = False
                #     print("sending first interrupt")
                #     await self._ws.send(json.dumps(audio_json))
                audio_json = {
                    "audio_data": base64.b64encode(audio_bytes).decode("utf-8"),
                    "start_seconds": audio_start,
                    "duration": audio_duration,
                    "audio_format": "pcm_16000",
                    "id": str(uuid.uuid4()),
                }
                audio_start += audio_duration
                asyncio.run_coroutine_threadsafe(self._ws.send(json.dumps(audio_json)), self._loop)
                self._audio_library.append(
                    (
                        audio_json["start_seconds"],
                        audio_data,
                    ),
                )
        except Exception as e:
            logging.error(f"Error sending audio data: {e}")
            raise asyncio.CancelledError()

    def recv_task(self):
        """
        Continuously receive and process video data from the WebSocket server.
        """
        start_time = 0.0
        silence_flag = True
        try:
            while not self._stop_event.is_set():
                if not self._ws:
                    time.sleep(0.1)
                    continue

                try:
                    msg = asyncio.run_coroutine_threadsafe(
                        asyncio.wait_for(self._ws.recv(), timeout=0.2), self._loop
                    ).result()
                except asyncio.TimeoutError:
                    continue

                first_image = self.image_output_stream.get_first_element_without_removing()
                if first_image and first_image.extra_tags["silence_flag"] and self._speaking:
                    self._speaking = False

                response_data: Dict[str, Any] = json.loads(msg)
                images = response_data.get("image_data", [])
                if not images[0]["silence_flag"]:
                    print("received frames: ", len(images), time.time())
                for image in images:
                    # Decode the base64 string to bytes
                    if image["silence_flag"] and not silence_flag:
                        print("silence flag to true", time.time())
                        silence_flag = True
                    elif not image["silence_flag"] and silence_flag:
                        print("silence flag to false", time.time())
                        self._speaking = True
                        silence_flag = False
                        diff = max(self.image_output_stream.qsize() - self.audio_output_stream.qsize(), 0)
                        print(self.image_output_stream.qsize(), self.audio_output_stream.qsize(), start_time)
                        i = 1
                        while True:
                            if not self.audio_output_stream.get_element_at_index(i):
                                break
                            if not self.image_output_stream.get_element_at_index(i + diff):
                                break
                            start_time -= image["duration"]
                        print(self.image_output_stream.qsize(), self.audio_output_stream.qsize(), start_time)
                    start_time = max(rt.Clock.get_playback_time(), start_time)
                    # print([image[x] for x in image if x != "image" and x != "audio"], time.time())
                    image_bytes = base64.b64decode(image["image"])
                    audio_bytes = base64.b64decode(image["audio"])
                    image_data = rt.ImageData(
                        data=image_bytes,
                        format="jpeg",
                        frame_rate=FRAME_RATE,
                        relative_start_time=start_time,
                        extra_tags={"frame_idx": image["frame_idx"], "silence_flag": image["silence_flag"]},
                    )
                    audio_data = rt.AudioData(
                        data=audio_bytes,
                        sample_rate=16000,
                        channels=1,
                        sample_width=2,
                        format="wav",
                        relative_start_time=start_time,
                    )
                    self.image_output_stream.put_nowait(image_data)
                    self.audio_output_stream.put_nowait(audio_data)
                    start_time += image["duration"]
                    # while (
                    #     self._audio_library
                    #     and image["start_seconds"] >= self._audio_library[0][0]
                    # ):
                    #     audio_data: rt.AudioData = self._audio_library.pop(0)[1]
                    #     audio_data.relative_start_time = start_time
                    #     self.audio_output_stream.put_nowait(audio_data)
                    # start_time += image["duration"]
        except Exception as e:
            logging.error(f"Error receiving video data: {e}")
            raise asyncio.CancelledError()

    def set_interrupt_stream(self, interrupt_stream: rt.VADStream):
        if isinstance(interrupt_stream, rt.VADStream):
            self.interrupt_queue = interrupt_stream
        else:
            raise ValueError("Interrupt stream must be a VADStream")
        self._interrupt_task = asyncio.create_task(self._interrupt())

    async def _interrupt(self):
        while True:
            vad_state: rt.VADState = await self.interrupt_queue.get()
            if vad_state == rt.VADState.SPEAKING and (self._speaking or not self.audio_input_stream.empty()):
                logging.info("Interrupting Deepreel")
                self._stop_event.set()
                while self._send_thread.is_alive() or self._recv_thread.is_alive():
                    logging.info("Waiting for threads to stop...")
                    await asyncio.sleep(0.05)  # Non-blocking wait
                while self.audio_input_stream.qsize() > 0:
                    self.audio_input_stream.get_nowait()
                diff = max(self.image_output_stream.qsize() - self.audio_output_stream.qsize(), 0)
                print(self.image_output_stream.qsize(), self.audio_output_stream.qsize())
                i = FRAME_RATE
                while True:
                    if not self.audio_output_stream.get_element_at_index(i):
                        break
                    if not self.image_output_stream.get_element_at_index(i + diff):
                        break

                logging.info("Done cancelling Deepreel")
                self._stop_event.clear()
                self._send_thread = threading.Thread(target=self.send_task)
                self._send_thread.start()
                self._recv_thread = threading.Thread(target=self.recv_task)
                self._recv_thread.start()


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
        # asyncio.get_event_loop().set_debug(True)
        # Initialize processing nodes
        deepgram_node = rt.WhisperSTT(
            sample_rate=8000, base_url="ws://35.94.117.196:8765/ws", api_key="test", min_silence_duration=50
        )
        vad_node = rt.SileroVAD(sample_rate=8000, min_volume=0)
        llm_node = rt.GroqLLM(
            system_prompt="You are a virtual assistant. Keep the response short and concise.",
            temperature=0.9,
        )
        token_aggregator_node = rt.TokenAggregator()
        tts_node = rt.CartesiaTTS(
            voice_id="95856005-0332-41b0-935f-352e296aa0df",
            output_sample_rate=16000,
        )
        deepreel_node = DeepreelPlugin(websocket_url="ws://13.89.58.206:8765/ws")

        # Set up the processing pipeline
        deepgram_stream = deepgram_node.run(audio_input_stream)
        vad_stream = vad_node.run(audio_input_stream.clone())

        message_stream = rt.map(message_stream, lambda x: json.loads(x).get("content"))
        deepgram_stream = rt.merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = llm_node.run(deepgram_stream)
        token_aggregator_stream = token_aggregator_node.run(llm_token_stream)

        tts_stream = tts_node.run(token_aggregator_stream)
        video_stream, audio_stream = deepreel_node.run(tts_stream)

        # llm_node.set_interrupt_stream(vad_stream)
        # token_aggregator_node.set_interrupt_stream(vad_stream.clone())
        # tts_node.set_interrupt_stream(vad_stream.clone())
        # deepreel_node.set_interrupt_stream(vad_stream.clone())

        return video_stream, audio_stream

    async def teardown(self):
        """
        Clean up resources when the bot is shutting down. Currently empty, but can be implemented if needed.
        """
        pass


if __name__ == "__main__":
    try:
        bot = DeepReelBot()
        bot.start()
    except Exception as e:
        pass
    except KeyboardInterrupt:
        pass
