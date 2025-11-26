import logging
import warnings

# --- Workaround für amqtt Warnungen ---
# Wir nutzen die "alte" stabile Config-Struktur, unterdrücken aber die Warnhinweise,
# da die "neue" Struktur in manchen Umgebungen zu Import-Fehlern führt.
warnings.filterwarnings("ignore", message=".*is deprecated.*")

import asyncio
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from amqtt.broker import Broker
from amqtt.client import MQTTClient

# --- Konfiguration ---
BASE_TOPIC = "home/mailbox"
TOPIC_WILDCARD = f"{BASE_TOPIC}/#"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Server")

# --- FastAPI Setup ---
app = FastAPI()
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


# --- MQTT Logik (Stabile Konfiguration) ---
BROKER_CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        },
    },
    "sys_interval": 0,  # 0 deaktiviert das interne System-Topic (spart Logs)
    # Wir nutzen die klassische Auth-Config, da diese zuverlässiger lädt als die Plugin-Struktur
    "auth": {
        "allow_anonymous": True,
        "password_file": None,
        "plugins": ["auth_anonymous"],
    },
    "topic-check": {"enabled": False},
}


class MailboxBackend:
    def __init__(self):
        self.client = MQTTClient()

    async def start_broker(self):
        try:
            self.broker = Broker(BROKER_CONFIG)
            await self.broker.start()
            logger.info("✅ MQTT Broker läuft auf Port 1883")
        except Exception as e:
            logger.error(f"Fehler beim Starten des Brokers: {e}")
            # Falls setuptools fehlt, geben wir einen Hinweis
            try:
                import setuptools
            except ImportError:
                logger.critical(
                    "ACHTUNG: 'setuptools' fehlt! Bitte in requirements.txt ergänzen."
                )
            raise e

    async def process_messages(self):
        try:
            await asyncio.sleep(2)  # Warte kurz auf Broker-Start
            await self.client.connect("mqtt://localhost:1883")
            await self.client.subscribe([(TOPIC_WILDCARD, 1)])
            logger.info("✅ Backend Client verbunden")

            while True:
                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name

                try:
                    payload = packet.payload.data.decode("utf-8")
                    if not payload:
                        continue
                    data = json.loads(payload)

                    frontend_data = {}

                    if topic.endswith("/status"):
                        frontend_data = data
                        logger.info(f"Status: {data.get('mailbox_state')}")

                    elif topic.endswith("/events/mail_drop"):
                        frontend_data = data
                        frontend_data["event_type"] = "mail_drop"
                        frontend_data["mailbox_state"] = data.get("new_state")
                        logger.info("EVENT: Post Einwurf!")

                    elif topic.endswith("/events/mail_collected"):
                        frontend_data = data
                        frontend_data["event_type"] = "mail_collected"
                        frontend_data["mailbox_state"] = data.get("new_state")
                        logger.info("EVENT: Post entnommen!")

                    if frontend_data:
                        await manager.broadcast(frontend_data)

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
        backend.start_broker(), backend.process_messages(), server.serve()
    )


if __name__ == "__main__":
    try:
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
