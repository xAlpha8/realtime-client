import asyncio
import functools
import inspect
import logging
from typing import Callable, List, Optional, Tuple, Union

from realtime.server import RealtimeServer
from realtime.streams import AudioStream, ByteStream, TextStream, VideoStream
from realtime.websocket.processors import WebsocketInputProcessor, WebsocketOutputProcessor
from realtime.websocket.server import create_and_run_server

logger = logging.getLogger(__name__)


def websocket(path: str = "/"):
    """
    Decorator for handling WebSocket connections.
    TODO: Add video support
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> None:
            try:
                audio_input_q = None
                video_input_q = None
                text_input_q = None
                kwargs = {}

                signature = inspect.signature(func)
                parameters = signature.parameters
                for name, param in parameters.items():
                    if param.annotation == AudioStream:
                        audio_input_q = AudioStream()
                        kwargs[name] = audio_input_q
                    elif param.annotation == VideoStream:
                        video_input_q = VideoStream()
                        kwargs[name] = video_input_q
                    elif param.annotation == TextStream:
                        text_input_q = TextStream()
                        kwargs[name] = text_input_q

                output_streams = await func(**kwargs)

                if not isinstance(output_streams, (list, tuple)):
                    output_streams = (output_streams,)

                aq, vq, tq = None, None, None
                for s in output_streams:
                    if isinstance(s, AudioStream):
                        aq = s
                    elif isinstance(s, VideoStream):
                        vq = s
                    elif isinstance(s, TextStream):
                        tq = s
                    elif isinstance(s, ByteStream):
                        bq = s

                # TODO: Update the default sample rate to be consistent across all plugins
                websocket_input_processor = WebsocketInputProcessor(audio_stream=audio_input_q, message_stream=text_input_q, video_stream=video_input_q)
                websocket_output_processor = WebsocketOutputProcessor(audio_stream=aq, message_stream=tq, video_stream=vq, byte_stream=bq)
                create_and_run_server(path, websocket_input_processor, websocket_output_processor)
                tasks = [websocket_input_processor.run(), websocket_output_processor.run()]
                await asyncio.gather(*tasks)

                await create_and_run_server(path, websocket_input_processor, websocket_output_processor)
            except Exception as e:
                logging.error(f"Error in websocket_endpoint: {e}")
                pass
        return wrapper


    return decorator
