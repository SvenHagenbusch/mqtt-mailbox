import asyncio
import json
import logging
from mailbox import Mailbox
import os
import warnings
from datetime import time
from typing import Literal

import uvicorn
from amqtt.client import MQTTClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError

# --- Workaround für amqtt Warnungen ---
# Wir nutzen die "alte" stabile Config-Struktur, unterdrücken aber die Warnhinweise,
# da die "neue" Struktur in manchen Umgebungen zu Import-Fehlern führt.
warnings.filterwarnings("ignore", message=".*is deprecated.*")

# --- Konfiguration ---
BASE_TOPIC = "home/mailbox"
TOPIC_WILDCARD = f"{BASE_TOPIC}/#"
BROKER_ADDRESS = os.getenv("BROKER_ADDRESS", "localhost:1883")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Server")


# Binary Protocol Format:
# ip: u32
# timestamp: (unix) u32
# distance: u16
# state: 3 bit -> u8
# success_rate: u8,
# baseline: u16
# confidence (u8) (0x0 bei collected & status)
class MailboxTelemetry(BaseModel):
    device_ip: str
    timestamp: int # unix timestamp
    distance: int  # u16
    state: Literal["empty", "has_mail", "full", "emptied"]
    success_rate: int  # u8
    baseline: int  # u16 bit
    confidence: int  # u8; 0 for collected & status

    @classmethod
    def from_byte_stream(cls, payload: bytes) -> "MailboxTelemetry":
        """
        Parse binary MQTT payload into MailboxTelemetry.

        Args:
            payload: Raw bytes from MQTT broker

        Returns:
            MailboxTelemetry instance
        """
        state = ""
        match payload[10]:
            case 0:
                state = "empty"
            case 1:
                state = "has_mail"
            case 2:
                state = "full"
            case 3:
                state = "emptied"
            case _:
                state = "empty"

        return MailboxTelemetry(
            device_ip=MailboxTelemetry.ip_string_from_bytes(payload[0:4]),
            timestamp=int.from_bytes(payload[4:8], byteorder='big', signed=False),
            distance=int.from_bytes(payload[8:10], byteorder='big', signed=False),
            state=state,
            success_rate=payload[11],
            baseline=int.from_bytes(payload[12:14], byteorder='big', signed=False),
            confidence=payload[14],
        )

    @classmethod
    def ip_string_from_bytes(cls, payload: bytes) -> str:
        # FUCKING LITTLE ENDIAN
        return (
            f"{int(payload[0])}.{int(payload[1])}.{int(payload[2])}.{int(payload[3])}"
        )

        # MailboxTelemetry.model_construct()

        # TODO: Implement binary parsing
        raise NotImplementedError("Binary parsing not yet implemented")


# --- FastAPI Setup ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.last_status = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        if self.last_status:
            await websocket.send_text(json.dumps(self.last_status))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        self.last_status.update(message)
        json_str = json.dumps(message)
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(json_str)
            except Exception:
                pass


manager = ConnectionManager()


# --- Web Routes ---
@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- MQTT Logik ---
class MailboxBackend:
    def __init__(self):
        self.client = MQTTClient()

    async def process_messages(self):
        try:
            await self.client.connect(f"mqtt://{BROKER_ADDRESS}")
            await self.client.subscribe([(TOPIC_WILDCARD, 1)])
            logger.info(f"✅ Backend Client verbunden mit {BROKER_ADDRESS}")

            while True:
                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name

                try:
                    # Get raw binary payload
                    payload = packet.payload.data
                    if not payload:
                        continue

                    # Parse binary telemetry data
                    telemetry = MailboxTelemetry.from_byte_stream(payload)
                    logger.info(
                        f"Received telemetry from {telemetry.device_ip}: state={telemetry.state}, distance={telemetry.distance}"
                    )

                    # Prepare data for frontend
                    frontend_data = telemetry.model_dump()

                    # Add event type based on topic
                    if topic.endswith("/events/mail_drop"):
                        frontend_data["event_type"] = "mail_drop"
                        logger.info(
                            f"EVENT: Post Einwurf! Confidence: {telemetry.confidence}"
                        )
                    elif topic.endswith("/events/mail_collected"):
                        frontend_data["event_type"] = "mail_collected"
                        logger.info(f"EVENT: Post entnommen!")
                    elif topic.endswith("/status"):
                        logger.info(f"Status: {telemetry.state}")

                    # Rename fields for frontend compatibility
                    frontend_data["mailbox_state"] = frontend_data.pop("state")

                    await manager.broadcast(frontend_data)

                except NotImplementedError:
                    logger.error(f"Binary parsing not yet implemented")
                except ValidationError as ve:
                    logger.error(f"Telemetry validation error on {topic}: {ve}")
                except Exception as e:
                    logger.error(f"Verarbeitungsfehler: {e}")

        except Exception as e:
            logger.error(f"Backend Fehler: {e}")


# --- Main Start Script ---
async def main():
    backend = MailboxBackend()
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    await asyncio.gather(backend.process_messages(), server.serve())


if __name__ == "__main__":
    try:
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
