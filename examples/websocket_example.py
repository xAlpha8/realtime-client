import json
import logging

import realtime as rt

logging.basicConfig(level=logging.INFO)


@rt.App()
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

    @rt.websocket()
    async def run(audio_input_stream: rt.AudioStream, message_stream: rt.TextStream):
        deepgram_node = rt.DeepgramSTT(sample_rate=audio_input_stream.sample_rate)
        llm_node = rt.GroqLLM(
            system_prompt="You are a virtual girlfriend.\
            You will always reply with a JSON object.\
            Each message has a text, facialExpression, and animation property.\
            The text property is a short response to the user (no emoji).\
            The different facial expressions are: smile, sad, angry, and default.\
            The different animations are: Talking_0, Talking_1, Talking_2, Crying, Laughing, Rumba, Idle, Terrified, and Angry.",
            temperature=0.9,
            response_format={"type": "json_object"},
            stream=False,
        )
        tts_node = rt.AzureTTS(stream=True)

        deepgram_stream = deepgram_node.run(audio_input_stream)
        deepgram_stream = rt.merge([deepgram_stream, message_stream])

        llm_token_stream, chat_history_stream = llm_node.run(deepgram_stream)

        json_text_stream = rt.map(llm_token_stream.clone(), lambda x: json.loads(x).get("text"))

        tts_stream, viseme_stream = tts_node.run(json_text_stream)

        llm_with_viseme_stream = rt.merge([llm_token_stream, viseme_stream])

        return tts_stream, llm_with_viseme_stream

    async def teardown(self):
        pass


if __name__ == "__main__":
    v = ReplayBot()
    v.start()
