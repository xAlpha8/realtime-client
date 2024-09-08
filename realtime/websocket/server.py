import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial

from fastapi import WebSocket

from realtime.server import RealtimeServer
from realtime.streams import TextStream
from realtime.websocket.processors import WebsocketInputProcessor, WebsocketOutputProcessor

logger = logging.getLogger(__name__)


async def websocket_handler(
        websocket: WebSocket,
        websocket_input_processor: WebsocketInputProcessor,
        websocket_output_processor: WebsocketOutputProcessor):
    RealtimeServer().add_connection()
    try:
        await websocket.accept()
        audio_metadata = await websocket.receive_json()
        # set the input track of these things

        # run the tasks
        iq = TextStream()
        oq = TextStream()

        async def receive_data():
            while True:
                data = await websocket.receive_json()
                await iq.put(data)

        async def send_data():
            while True:
                data = await oq.get()
                await websocket.send_json(data)

        websocket_input_processor.setInputTrack(iq)
        websocket_input_processor.sample_rate = audio_metadata.get("input_sample_rate", 48000)
        websocket_output_processor.setOutputTrack(oq)
        websocket_output_processor.sample_rate = audio_metadata.get("output_sample_rate", 48000)

        tasks = [
            asyncio.create_task(receive_data()),
            asyncio.create_task(send_data())
        ]

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logging.error("websocket: CancelledError")
    except Exception as e:
        logging.error("websocket: Error in websocket: ", e)
    finally:
        logging.info("websocket: Removing connection")
        RealtimeServer().remove_connection()


@asynccontextmanager
async def on_shutdown():
    yield
    # close peer connections
    logging.info("websocket: Removing connection")
    RealtimeServer().remove_connection()


def create_and_run_server(path, websocket_input_processor, websocket_output_processor):
    fastapi_app = RealtimeServer().get_app()
    fastapi_app.websocket(path)(partial(websocket_handler, websocket_input_processor=websocket_input_processor,
                                        websocket_output_processor=websocket_output_processor))
    fastapi_app.add_event_handler("shutdown", on_shutdown)
