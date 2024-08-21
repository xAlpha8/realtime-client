import asyncio
import json
import websockets

async def websocket_client():
    uri = "ws://localhost:8080/"
    async with websockets.connect(uri) as websocket:
        # Sending a message
        await websocket.send(json.dumps({"type": "message", "data": "Hello Server!"}))
        print("Message sent to the server")

        # Receiving a response
        while True:
            response = await websocket.recv()
            print("Received from server:", response)

# Running the client
asyncio.run(websocket_client())