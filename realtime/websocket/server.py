import asyncio
import logging
from contextlib import asynccontextmanager
from functools import partial

from realtime.server import RealtimeServer

logger = logging.getLogger(__name__)

async def websocket_handler(websocket, websocket_input_processor, websocket_output_processor):
    RealtimeServer().add_connection()
    try:
        await websocket.accept()
        audio_metadata = await websocket.receive_json()

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
    fastapi_app.websocket(path)(partial(websocket_handler, websocket_input_processor=websocket_input_processor, websocket_output_processor=websocket_output_processor))
    fastapi_app.add_event_handler("shutdown", on_shutdown)
