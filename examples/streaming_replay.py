import json
import logging

import realtime as rt

logging.basicConfig(level=logging.INFO)

"""
Wrapping your class with @realtime.App() will tell the realtime server which functions to run.
"""


@rt.App()
class ReplayBot:
    async def setup(self):
        pass

    @rt.streaming_endpoint()
    async def run(self, audio_input_queue: rt.AudioStream, video_input_queue: rt.VideoStream, text_input_queue: rt.TextStream):
        text_stream_with_notif = rt.map(text_input_queue, lambda x: { "text": x, "notification": "<div>Hello</div>"})
        text_stream_output = rt.map(text_stream_with_notif, lambda x: json.dumps(x))
        return (audio_input_queue, video_input_queue, text_stream_output)

    async def teardown(self):
        pass


if __name__ == "__main__":
    ReplayBot().start()
