import time


class Data:
    pass

class AudioData(Data):

    def __init__(self, data: bytes, output_stream: str = None):
        if not isinstance(data, bytes):
            raise ValueError("AudioData must be bytes")
        self.data = data
        self.timestamp = time.time()
        self.output_stream = output_stream


class ImageData(Data):
    
    def __init__(self, data: bytes, output_stream: str = None):
        if not isinstance(data, bytes):
            raise ValueError("ImageData must be bytes")
        self.data = data
        self.timestamp = time.time()
        self.output_stream = output_stream
class TextData(Data):
    def __init__(self, data: str, output_stream: str = None):
        if not isinstance(data, str):
            raise ValueError("TextData must be str")
        self.data = data
        self.timestamp = time.time()
        self.output_stream = output_stream
class ByteData(Data):
    def __init__(self, data: bytes, output_stream: str = None):
        if not isinstance(data, bytes):
            raise ValueError("ByteData must be bytes")
        self.data = data
        self.timestamp = time.time()
        self.output_stream = output_stream