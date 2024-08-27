import asyncio
import json
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO)

from deepreel_plugin import DeepreelPlugin

import realtime
from realtime.ops.map import map
from realtime.ops.merge import merge
from realtime.plugins.azure_tts import AzureTTS
from realtime.plugins.deepgram_stt import DeepgramSTT
from realtime.plugins.fireworks_llm import FireworksLLM
from realtime.streams import AudioStream, Stream, TextStream


@realtime.App()
class DeepReelBot:
    async def setup(self):
        pass

    @realtime.streaming_endpoint()
    async def run(self, audio_input_stream: AudioStream, message_stream: TextStream) -> Tuple[Stream, ...]:
        deepgram_node = DeepgramSTT(sample_rate=audio_input_stream.sample_rate)
        llm_node = FireworksLLM(
            system_prompt="You are a virtual assistant.\
            You will always reply with a JSON object.\
            Each message has a text, facialExpression, and animation property.\
            The text property is a short response to the user (no emoji).\
            The different facial expressions are: smile, sad, angry, surprised, funnyFace, and default.\
            The different animations are: Talking_0, Talking_1, Talking_2, Crying, Laughing, Rumba, Idle, Terrified, and Angry.",
            temperature=0.9,
            response_format={"type": "json_object"},
            stream=False,
        )
        tts_node = AzureTTS(stream=False, voice_id="en-US-EricNeural")
        deepreel_node = DeepreelPlugin(websocket_url="ws://localhost:8765/ws")

        deepgram_stream = await deepgram_node.run(audio_input_stream)
        deepgram_stream = merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = await llm_node.run(deepgram_stream)

        json_text_stream = map(await llm_token_stream.clone(), lambda x: json.loads(x).get("text"))

        tts_stream, _ = await tts_node.run(json_text_stream)
        video_stream, audio_stream = await deepreel_node.run(tts_stream)

        return video_stream, audio_stream

    async def teardown(self):
        pass


if __name__ == "__main__":
    asyncio.run(DeepReelBot().run())
