# MQTT Mailbox Server

Backend server for IoT mailbox monitoring system using binary telemetry protocol over MQTT.

## Overview

This server receives binary telemetry data from ESP-based mailbox sensors via MQTT and provides a real-time web dashboard. The system uses a custom 15-byte binary protocol to minimize bandwidth usage and extend ESP battery life.

## Binary Protocol Format

All telemetry messages use **big-endian** byte order:

| Field        | Type | Bytes | Description                          |
|--------------|------|-------|--------------------------------------|
| ip           | u32  | 4     | Device IP address                    |
| timestamp    | u32  | 4     | Unix timestamp                       |
| distance     | u16  | 2     | Distance measurement (mm)            |
| state        | u8   | 1     | Mailbox state (0-3)                  |
| success_rate | u8   | 1     | Success rate (0-255)                 |
| baseline     | u16  | 2     | Baseline distance (mm)               |
| confidence   | u8   | 1     | Confidence level (0-255)             |

**Total: 15 bytes**

### State Values
- `0` = empty
- `1` = has_mail
- `2` = full
- `3` = emptied

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Start the Server

```bash
# Start MQTT broker and web server
python server.py

# Or with Docker
docker-compose up
```

The web dashboard will be available at `http://localhost:8000`

### 3. Test with Simulated Data

```bash
# Interactive menu
./mosquitto.sh

# Or publish specific events
./mosquitto.sh dropped    # Simulate mail drop
./mosquitto.sh collected  # Simulate mail collection
./mosquitto.sh status     # Publish status update
```

## Project Structure

```
mqtt-mailbox-server/
├── server.py                 # Main FastAPI server & MQTT client
├── mosquitto.sh              # MQTT testing script
├── templates/                # Web UI templates
├── static/                   # Static assets
└── testing/
    ├── encode.py             # Binary protocol encoder/decoder
    ├── test_telemetry.py     # Unit tests
    ├── test_publish.sh       # Local payload testing
    └── README.md             # Detailed testing docs
```

## Configuration

Set environment variables:

```bash
# MQTT Broker address
export BROKER_ADDRESS="localhost:1883"

# Or edit in server.py
BROKER_ADDRESS = "your-broker:1883"
```

## MQTT Topics

- `home/mailbox/status` - Regular status updates
- `home/mailbox/events/mail_dropped` - Mail drop events
- `home/mailbox/events/mail_collected` - Mail collection events

## Development

### Running Tests

```bash
cd testing
pytest test_telemetry.py -v
```

### Encoding/Decoding Payloads

```bash
# Encode JSON to binary hex
echo '{"device_ip":"192.168.1.100","timestamp":1704067200,"distance":250,"state":"empty","success_rate":95,"baseline":300,"confidence":85}' | \
  python testing/encode.py encode

# Decode hex to JSON
python testing/encode.py decode --hex c0a801646592008000fa5f012c55 --pretty

# Test payload generation locally
cd testing
./test_publish.sh all
```

### Implementing the Parser

The binary parsing method needs to be implemented in `server.py`:

```python
@classmethod
def from_byte_stream(cls, payload: bytes) -> "MailboxTelemetry":
    """Parse binary MQTT payload into MailboxTelemetry."""
    import struct
    
    # Unpack big-endian format
    ip_u32, timestamp_u32, distance_u16, state_u8, success_rate_u8, baseline_u16, confidence_u8 = \
        struct.unpack('>IIHBBHB', payload)
    
    # Convert IP to string
    device_ip = f"{(ip_u32 >> 24) & 0xFF}.{(ip_u32 >> 16) & 0xFF}.{(ip_u32 >> 8) & 0xFF}.{ip_u32 & 0xFF}"
    
    # Convert state to string
    state_map = {0: "empty", 1: "has_mail", 2: "full", 3: "emptied"}
    state = state_map[state_u8]
    
    # Convert timestamp to time object (or keep as int depending on your needs)
    from datetime import datetime
    timestamp = datetime.fromtimestamp(timestamp_u32).time()
    
    return cls(
        device_ip=device_ip,
        timestamp=timestamp,
        distance=distance_u16,
        state=state,
        success_rate=success_rate_u8,
        baseline=baseline_u16,
        confidence=confidence_u8
    )
```

## API Endpoints

- `GET /` - Web dashboard
- `WebSocket /ws` - Real-time telemetry updates

## Technologies

- **FastAPI** - Web framework
- **amqtt** - MQTT client library
- **WebSockets** - Real-time communication
- **Pydantic** - Data validation
- **pytest** - Testing framework

## Documentation

- [Testing Guide](testing/README.md) - Detailed testing documentation
- [Binary Protocol](testing/README.md#binary-protocol-format) - Protocol specification

## License

MIT