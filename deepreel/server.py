import base64
import io
import os

import av
import uvicorn
from fastapi import FastAPI, WebSocket

server_app = FastAPI()
parent_dir = os.path.dirname(os.path.abspath(__file__))


async def sync(container, video_time_base, duration, video_frame):
    offset = round(duration / video_time_base) + video_frame.pts if video_frame else round(duration / video_time_base)
    print("offset", offset)
    frames = []
    if video_frame and offset < video_frame.pts:
        return None, video_frame
    while video_frame is None or video_frame.pts < offset:
        video_frame = next(container.decode(container.streams.video[0]))
        pil_image = video_frame.to_image()
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        pil_image.save(img_byte_arr, format="JPEG")  # You can change the format as needed
        img_byte_arr = img_byte_arr.getvalue()
        final_img = base64.b64encode(img_byte_arr).decode("utf-8")
        frames.append(final_img)
    return frames, video_frame


@server_app.websocket("/ws")
async def receiver(websocket: WebSocket):
    """WebSocket endpoint for receiving audio data and sending back images."""
    await websocket.accept()

    container = av.open(f"{parent_dir}/videoplayback.mp4", mode="r")
    video_time_base = container.streams.video[0].time_base
    framerate = container.streams.video[0].average_rate

    # Handle audio data received from the client
    video_frame = None
    while True:
        message = await websocket.receive_json()
        print("audio", message["start_seconds"], message["end_seconds"])
        images, video_frame = await sync(
            container, video_time_base, message["end_seconds"] - message["start_seconds"], video_frame
        )
        if images is None:
            continue
        response = {"image_data": []}
        start_seconds = message["start_seconds"]
        print("images", len(images))
        for i in range(len(images)):
            image = images[i]
            response["image_data"].append(
                {
                    "image": image,
                    "start_seconds": start_seconds,
                    "duration": float(1 / framerate),
                }
            )
            start_seconds += 1 / framerate
            if i % 10 == 9:
                await websocket.send_json(response)
                response = {"image_data": []}
        if response["image_data"]:
            await websocket.send_json(response)


@server_app.on_event("startup")
async def startup():
    """Placeholder for startup event."""
    pass


# Run the FastAPI app
if __name__ == "__main__":
    uvicorn.run(server_app, host="0.0.0.0", port=8765, log_level="debug")
