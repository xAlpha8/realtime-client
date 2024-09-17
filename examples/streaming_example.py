import asyncio
import logging
from typing import Tuple

import outspeed as op

logging.basicConfig(level=logging.INFO)

"""
Wrapping your class with @realtime.App() will tell the realtime server which functions to run.
"""


@op.App()
class ReplayBot:
    async def setup(self):
        pass

    @op.streaming_endpoint()
    async def run(self, audio_input_queue: rt.AudioStream, video_input_queue: rt.VideoStream):
        return (audio_input_queue, video_input_queue, None)

    async def teardown(self):
        pass


if __name__ == "__main__":
    ReplayBot().start()
