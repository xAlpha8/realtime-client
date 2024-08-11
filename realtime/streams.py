import asyncio
from typing import List
import uuid
from realtime.data import AudioData, ImageData, TextData, ByteData

class Stream(asyncio.Queue):
    """An asynchronous queue where objects added to it are also added to its copies."""

    def __init__(self, id: str = None):
        super().__init__()
        self.id = id or str(uuid.uuid4())
        self._clones: List[Stream] = []


class AudioStream(Stream):
    type = "audio"

    def clone(self):
        """Create a copy of this queue."""
        clone = AudioStream()
        self._clones.append(clone)
        return clone

    async def put(self, item):
        """Put an item in all queues of all instances."""
        self.put_nowait(item)

    def put_nowait(self, item):
        """Put an item in all queues of all instances."""
        if type(item) != AudioData:
            raise ValueError("AudioStream can only accept AudioData")
        super().put_nowait(item)
        for clone in self._clones:
            clone.put_nowait(item)

class VideoStream(Stream):
    type = "video"

    def clone(self):
        """Create a copy of this queue."""
        clone = VideoStream()
        self._clones.append(clone)
        return clone

    async def put(self, item):
        """Put an item in all queues of all instances."""
        self.put_nowait(item)

    def put_nowait(self, item):
        """Put an item in all queues of all instances."""
        if type(item) != ImageData:
            raise ValueError("VideoStream can only accept ImageData")
        super().put_nowait(item)
        for clone in self._clones:
            clone.put_nowait(item)


class TextStream(Stream):
    type = "text"

    def clone(self):
        """Create a copy of this queue."""
        clone = TextStream()
        self._clones.append(clone)
        return clone

    async def put(self, item):
        """Put an item in all queues of all instances."""
        self.put_nowait(item)

    def put_nowait(self, item):
        """Put an item in all queues of all instances."""
        if type(item) != TextData:
            raise ValueError("TextStream can only accept TextData")
        super().put_nowait(item)
        for clone in self._clones:
            clone.put_nowait(item)


class ByteStream(Stream):
    type = "bytes"

    def clone(self):
        """Create a copy of this queue."""
        clone = ByteStream()
        self._clones.append(clone)
        return clone

    async def put(self, item):
        """Put an item in all queues of all instances."""
        self.put_nowait(item)

    def put_nowait(self, item):
        """Put an item in all queues of all instances."""
        if type(item) != ByteData:
            raise ValueError("ByteStream can only accept ByteData")
        super().put_nowait(item)
        for clone in self._clones:
            clone.put_nowait(item)
