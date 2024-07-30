import os
import uvicorn

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI


class RealtimeServer:
    _instance = None  # Class variable to hold the single instance
    _initialized = False  # Flag to check if __init__ has been called

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RealtimeServer, cls).__new__(cls)
            cls._instance.__init__()
            cls._initialized = True
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.app = FastAPI()
        self.app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
        self.HOSTNAME = "0.0.0.0"
        self.PORT = int(os.getenv("HTTP_PORT", 8080))

    async def start(self):
        # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # ssl_context.load_cert_chain(os.environ["SSL_CERT_PATH"], keyfile=os.environ["SSL_KEY_PATH"])
        self.server = uvicorn.Server(
            config=uvicorn.Config(
                self.app,
                host=self.HOSTNAME,
                port=self.PORT,
                log_level="debug",
                # ssl_keyfile=os.environ["SSL_KEY_PATH"],
                # ssl_certfile=os.environ["SSL_CERT_PATH"],
            )
        )
        await self.server.serve()

    def get_app(self):
        return self.app
