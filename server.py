import logging
import os
import warnings


import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional
from amqtt.client import MQTTClient

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

# --- Pydantic Models ---
class MailboxStatus(BaseModel):
    device_ip: Optional[str] = None
    timestamp: Optional[str] = None
    distance_cm: float
    baseline_cm: Optional[float] = 40.0
    threshold_cm: Optional[float] = None
    success_rate: float
    mailbox_state: Literal["empty", "has_mail", "full", "emptied"]


class MailDropEvent(BaseModel):
    device_ip: Optional[str] = None
    timestamp: Optional[str] = None
    distance_cm: float
    baseline_cm: Optional[float] = 40.0
    duration_ms: Optional[int] = None
    confidence: Optional[float] = None
    success_rate: Optional[float] = None
    new_state: Optional[Literal["empty", "has_mail", "full", "emptied"]] = None
    mailbox_state: Optional[Literal["empty", "has_mail", "full", "emptied"]] = None


class MailCollectedEvent(BaseModel):
    device_ip: Optional[str] = None
    timestamp: Optional[str] = None
    before_cm: float
    after_cm: float
    baseline_cm: Optional[float] = 40.0
    duration_ms: Optional[int] = None
    success_rate: Optional[float] = None
    new_state: Optional[Literal["empty", "has_mail", "full", "emptied"]] = None
    mailbox_state: Optional[Literal["empty", "has_mail", "full", "emptied"]] = None


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
                    payload = packet.payload.data.decode("utf-8")
                    if not payload:
                        continue
                    data = json.loads(payload)
                    logger.info(f"received json: {data}")

                    frontend_data = None

                    try:
                        if topic.endswith("/status"):
                            status = MailboxStatus(**data)
                            frontend_data = status.model_dump()
                            logger.info(f"Status: {status.mailbox_state}")

                        elif topic.endswith("/events/mail_drop"):
                            event = MailDropEvent(**data)
                            frontend_data = event.model_dump()
                            frontend_data["event_type"] = "mail_drop"
                            # Use new_state if available, otherwise use mailbox_state
                            frontend_data["mailbox_state"] = event.new_state or event.mailbox_state
                            logger.info(f"EVENT: Post Einwurf! Confidence: {event.confidence}")

                        elif topic.endswith("/events/mail_collected"):
                            event = MailCollectedEvent(**data)
                            frontend_data = event.model_dump()
                            frontend_data["event_type"] = "mail_collected"
                            # Use new_state if available, otherwise use mailbox_state
                            frontend_data["mailbox_state"] = event.new_state or event.mailbox_state
                            logger.info(f"EVENT: Post entnommen! Duration: {event.duration_ms}ms")

                        if frontend_data:
                            await manager.broadcast(frontend_data)

                    except ValidationError as ve:
                        logger.error(f"Pydantic validation error on {topic}: {ve}")
                        logger.error(f"Received data: {data}")
                        # Fallback: send raw data with event_type added
                        if topic.endswith("/events/mail_drop"):
                            data["event_type"] = "mail_drop"
                        elif topic.endswith("/events/mail_collected"):
                            data["event_type"] = "mail_collected"
                        await manager.broadcast(data)

                except json.JSONDecodeError:
                    logger.warning(f"Ungültiges JSON auf {topic}")
                except Exception as e:
                    logger.error(f"Verarbeitungsfehler: {e}")

        except Exception as e:
            logger.error(f"Backend Fehler: {e}")


# --- Main Start Script ---
async def main():
    backend = MailboxBackend()
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    await asyncio.gather(
        backend.process_messages(), server.serve()
    )


if __name__ == "__main__":
    try:
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
