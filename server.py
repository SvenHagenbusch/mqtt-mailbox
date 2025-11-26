import asyncio
import json
import logging
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
    """Verwaltet aktive Web-Verbindungen zum Dashboard"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.last_status = {}  # Speichert den letzten Status für neue Verbindungen

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Sende sofort den letzten bekannten Status, falls vorhanden
        if self.last_status:
            await websocket.send_text(json.dumps(self.last_status))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sendet JSON-Daten an alle verbundenen Browser"""
        # Aktualisiere den Cache für neue User
        self.last_status.update(message)

        json_str = json.dumps(message)
        for connection in self.active_connections:
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
            # Wir erwarten keine Nachrichten vom Browser, müssen die Verbindung aber offen halten
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- MQTT Logik ---
BROKER_CONFIG = {
    "listeners": {"default": {"type": "tcp", "bind": "0.0.0.0:1883"}},
    "sys_interval": 10,
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
        self.broker = Broker(BROKER_CONFIG)
        await self.broker.start()
        logger.info("✅ MQTT Broker läuft auf Port 1883")

    async def process_messages(self):
        try:
            await self.client.connect("mqtt://localhost:1883")
            await self.client.subscribe([(TOPIC_WILDCARD, 1)])
            logger.info("✅ Backend Client verbunden")

            while True:
                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name

                try:
                    payload = packet.payload.data.decode("utf-8")
                    data = json.loads(payload)

                    # Daten für das Frontend aufbereiten
                    frontend_data = {}

                    if topic.endswith("/status"):
                        # Status Update
                        frontend_data = data  # Wir übernehmen die Daten 1:1
                        logger.info(f"Status: {data.get('mailbox_state')}")

                    elif topic.endswith("/events/mail_drop"):
                        # Event: Post eingeworfen
                        frontend_data = data
                        frontend_data["event_type"] = "mail_drop"
                        frontend_data["mailbox_state"] = data.get(
                            "new_state"
                        )  # Status sofort aktualisieren
                        logger.info("EVENT: Post Einwurf!")

                    elif topic.endswith("/events/mail_collected"):
                        # Event: Post entnommen
                        frontend_data = data
                        frontend_data["event_type"] = "mail_collected"
                        frontend_data["mailbox_state"] = data.get("new_state")
                        logger.info("EVENT: Post entnommen!")

                    # An alle Browser senden
                    if frontend_data:
                        await manager.broadcast(frontend_data)

                except Exception as e:
                    logger.error(f"Fehler bei Verarbeitung: {e}")

        except Exception as e:
            logger.error(f"Backend Fehler: {e}")


# --- Main Start Script ---
async def main():
    # 1. Initialisiere Backend Logik
    backend = MailboxBackend()

    # 2. Konfiguriere Uvicorn (Webserver)
    # Wir müssen uvicorn manuell starten, damit es im selben Loop wie MQTT läuft
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # 3. Starte alles parallel
    await asyncio.gather(
        backend.start_broker(), backend.process_messages(), server.serve()
    )


if __name__ == "__main__":
    try:
        # Windows Fix für asyncio Policies
        import sys

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(main())
    except KeyboardInterrupt:
        pass
