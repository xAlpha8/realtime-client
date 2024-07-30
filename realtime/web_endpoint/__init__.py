import functools
import logging

from realtime.server import RealtimeServer

logger = logging.getLogger(__name__)


def web_endpoint(method: str = "POST", path: str = "/"):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            fastapi_app = RealtimeServer().get_app()
            print("fastapi_app.routes", fastapi_app, fastapi_app.routes)
            fastapi_app.add_api_route(path, func, methods=[method])
            print("fastapi_app.routes after", fastapi_app, fastapi_app.routes)

        return wrapper

    return decorator
