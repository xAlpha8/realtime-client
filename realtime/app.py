import asyncio
import logging
from typing import Type
from realtime.server import RealtimeServer


def App():
    def wrapper(user_cls: Type):
        def construct(*args, **kwargs):
            new_class = RealtimeApp(user_cls=user_cls, *args, **kwargs)
            return new_class

        return construct

    return wrapper


class RealtimeApp:
    functions = []

    def __init__(self, user_cls, *args, **kwargs):
        self._user_cls = user_cls
        # self._realtime_functions = RealtimeFunction.get_realtime_functions_from_class(user_cls=_user_cls)
        self._user_cls_instance = self._user_cls(*args, **kwargs)

    def __getattr__(self, k):
        if hasattr(self, k):
            return getattr(self, k)
        elif hasattr(self._user_cls_instance, k):
            return getattr(self._user_cls_instance, k)
        else:
            raise AttributeError(k)

    def start(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._user_cls_instance.setup())
            loop.run_until_complete(asyncio.gather(RealtimeServer().start(), self._user_cls_instance.run()))
            loop.run_until_complete(self._user_cls_instance.teardown())
        except Exception as e:
            logging.error(e)
            loop.run_until_complete(RealtimeServer().shutdown())
