import base64
import fractions
import io
import time
from typing import Union, Optional

import numpy as np
from av import AudioFrame, VideoFrame
from PIL import Image
from realtime.utils.clock import Clock


# Define a class to handle audio data with various utilities
class AudioData:
    def __init__(
        self,
        data: Union[bytes, AudioFrame],
        sample_rate: int = 8000,
        channels: int = 1,
        sample_width: int = 2,
        format: str = "wav",
        relative_start_time: Optional[float] = None,
    ):
        # Validate input types
        if not isinstance(data, (bytes, AudioFrame)):
            raise ValueError("AudioData data must be bytes or av.AudioFrame")
        self.data = data
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.format = format
        self.relative_start_time = relative_start_time or Clock.get_playback_time()

    def get_bytes(self) -> bytes:
        # Convert audio data to bytes
        if isinstance(self.data, bytes):
            return self.data
        elif isinstance(self.data, AudioFrame):
            return self.data.to_ndarray().tobytes()
        else:
            raise ValueError("AudioData data must be bytes or av.AudioFrame")

    def get_duration_seconds(self) -> float:
        # Calculate the duration of the audio in seconds
        audio_bytes = self.get_bytes()
        return len(audio_bytes) / (self.sample_rate * self.channels * self.sample_width)

    def get_base64(self) -> str:
        # Encode audio bytes to base64
        return base64.b64encode(self.get_bytes()).decode("utf-8")

    def get_start_seconds(self) -> float:
        # Get the start time of the audio in seconds
        return self.relative_start_time

    def get_pts(self) -> int:
        # Get the pts of the audio frame
        return int(self.relative_start_time * self.sample_rate)

    def get_frame(self) -> AudioFrame:
        # Convert audio data to an AudioFrame
        if isinstance(self.data, AudioFrame):
            self.data.pts = self.get_pts()
            return self.data
        elif isinstance(self.data, bytes):
            if len(self.data) < 2:
                raise ValueError("AudioData data must be at least 2 bytes")
            if len(self.data) % 2 != 0:
                audio_data = self.data[:-1]
            else:
                audio_data = self.data

            array = np.frombuffer(audio_data, dtype=np.int16).reshape(1, -1)  # mono has 1 channel

            if self.channels == 2:
                channel_layout = "stereo"
            elif self.channels == 1:
                channel_layout = "mono"
            else:
                raise ValueError("AudioData channels must be 1 or 2")

            if self.format == "wav":
                format = "s16"
            elif self.format == "opus":
                format = "opus"
            else:
                raise ValueError("AudioData format must be wav or opus")

            frame = AudioFrame.from_ndarray(array, format=format, layout=channel_layout)
            frame.sample_rate = self.sample_rate
            frame.pts = self.get_pts()
            frame.time_base = fractions.Fraction(1, self.sample_rate)
            return frame
        else:
            raise ValueError("AudioData data must be bytes or av.AudioFrame")


# Define a class to handle video data with various utilities
class ImageData:
    def __init__(
        self,
        data: Union[np.ndarray, VideoFrame, Image.Image, bytes],
        width: int = 640,
        height: int = 480,
        frame_rate: int = 30,
        format: str = "jpeg",
        relative_start_time: Optional[float] = None,
    ):
        # Validate input types
        if not isinstance(data, (np.ndarray, VideoFrame, Image.Image, bytes)):
            raise ValueError("VideoData data must be np.ndarray, av.VideoFrame, PIL.Image.Image or bytes")
        self.data = data
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
        self.format = format
        self.relative_start_time = relative_start_time or Clock.get_playback_time()

    def get_pts(self) -> int:
        # Get the pts of the video frame
        return int(self.relative_start_time * self.frame_rate)

    def get_frame(self) -> VideoFrame:
        # Convert video bytes to a VideoFrame
        if isinstance(self.data, bytes):
            pil_image = Image.open(io.BytesIO(self.data), formats=[self.format])
            image_frame = VideoFrame.from_image(pil_image)
            image_frame.pts = self.get_pts()
            image_frame.time_base = fractions.Fraction(1, self.frame_rate)
            return image_frame
        elif isinstance(self.data, np.ndarray):
            return Image.fromarray(self.data)
        elif isinstance(self.data, Image.Image):
            return VideoFrame.from_image(self.data)
        elif isinstance(self.data, VideoFrame):
            return self.data
        else:
            raise ValueError("VideoData data must be bytes or np.ndarray")

    def get_duration_seconds(self) -> float:
        # Calculate the duration of the video in seconds
        return 1.0 / self.frame_rate


# Define a class to handle text data with various utilities
class TextData:
    def __init__(
        self,
        data: Optional[str] = None,
        absolute_time: Optional[float] = None,
        relative_time: Optional[float] = None,
    ):
        # Validate input types
        if data is not None and not isinstance(data, str):
            raise ValueError("TextData data must be str")
        self.data = data
        self.absolute_time = absolute_time or time.time()
        self.relative_time = relative_time or 0.0
