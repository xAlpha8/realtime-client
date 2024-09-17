import json

import realtime as rt


def check_and_load(x):
    print(f"Input: {x}")
    print(f"Input type: {type(x)}")
    res = json.loads(x)
    print(f"Parsed JSON: {res}")
    text = res.get("text")
    print(f"Extracted text: {text}")
    print(f"Text type: {type(text)}")
    return text


@rt.App()
class Chatbot:
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
    async def run(self, audio_input_stream: rt.AudioStream, message_stream: rt.TextStream):
        deepgram_node = rt.DeepgramSTT(sample_rate=audio_input_stream.sample_rate)
        llm_node = rt.GroqLLM(
            system_prompt="You are a language tutor who teaches English.\
            You will always reply with a JSON object.\
            Each message has a text and facialExpression property.\
            The text property is a response to the user (no emoji).\
            The different facial expressions are: smile, sad, angry, and default.",
            temperature=0.9,
            response_format={"type": "json_object"},
            stream=False,
        )
        lip_sync_node = rt.LipSyncPhonetics()
        viseme_to_audio_node = rt.VisemeToAudio()

        # tts_node = rt.AzureTTS(stream=True)

        deepgram_stream = deepgram_node.run(audio_input_stream)
        combined_text_stream = rt.merge([deepgram_stream, message_stream])

        llm_token_stream, _ = llm_node.run(combined_text_stream)

        json_text_stream = rt.map(llm_token_stream, check_and_load)

        lip_syncd_stream = lip_sync_node.run(json_text_stream)

        viseme_to_audio_stream = viseme_to_audio_node.run(lip_syncd_stream)

        return _, viseme_to_audio_stream

    async def teardown(self):
        pass


if __name__ == "__main__":
    v = Chatbot()
    v.start()
