import json
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO)

from deepreel_plugin import DeepreelPlugin

import realtime as rt


@rt.App()
class DeepReelBot:
    async def setup(self):
        pass

    @rt.streaming_endpoint()
    async def run(self, audio_input_stream: rt.AudioStream, message_stream: rt.TextStream):
        deepgram_node = rt.DeepgramSTT(sample_rate=audio_input_stream.sample_rate)
        llm_node = rt.GroqLLM(
            system_prompt="You are a virtual assistant. Keep the response short and concise.",
            temperature=0.9,
            stream=False,
        )
        token_aggregator_node = rt.TokenAggregator()
        tts_node = rt.CartesiaTTS()
        deepreel_node = DeepreelPlugin(websocket_url="ws://localhost:8765/ws")

        deepgram_stream = deepgram_node.run(audio_input_stream)
        message_stream = rt.map(message_stream, lambda x: json.loads(x).get("content"))
        deepgram_stream = rt.merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = llm_node.run(deepgram_stream)
        token_aggregator_stream = token_aggregator_node.run(llm_token_stream)

        tts_stream = tts_node.run(token_aggregator_stream)
        video_stream, audio_stream = deepreel_node.run(tts_stream)

        return video_stream, audio_stream

    async def teardown(self):
        pass


if __name__ == "__main__":
    bot = DeepReelBot()
    bot.start()
