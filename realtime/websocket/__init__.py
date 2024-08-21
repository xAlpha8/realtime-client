import asyncio
import functools
import logging
from realtime.server import RealtimeServer


logger = logging.getLogger(__name__)


def websocket(path: str = "/"):
    def decorator(func):
        fastapi_app = RealtimeServer().get_app()
        fastapi_app.websocket(path)(func)

    return decorator
