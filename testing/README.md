# Testing Utilities

This directory contains testing utilities for the MQTT Mailbox binary protocol.

## Files

- **`encode.py`**: CLI tool and library for encoding/decoding binary payloads
- **`test_telemetry.py`**: Unit tests for `MailboxTelemetry.from_byte_stream()`
- **`example_data.json`**: Example telemetry data for testing

## Binary Protocol Format

The protocol uses **big-endian** byte order with the following structure (15 bytes total):

| Field        | Type | Bytes | Description                          |
|--------------|------|-------|--------------------------------------|
| ip           | u32  | 4     | Device IP address                    |
| timestamp    | u32  | 4     | Unix timestamp                       |
| distance     | u16  | 2     | Distance measurement (mm)            |
| state        | u8   | 1     | Mailbox state (0-3, uses 3 bits)     |
| success_rate | u8   | 1     | Success rate (0-255)                 |
| baseline     | u16  | 2     | Baseline distance (mm)               |
| confidence   | u8   | 1     | Confidence level (0-255, 0 for status) |

### State Values

- `0` = `empty`
- `1` = `has_mail`
- `2` = `full`
- `3` = `emptied`

## Using encode.py

### As a Library

```python
from encode import create_binary_payload, decode_binary_payload

# Encode data
data = {
    "device_ip": "192.168.1.100",
    "timestamp": 1704067200,
    "distance": 250,
    "state": "empty",
    "success_rate": 95,
    "baseline": 300,
    "confidence": 85
}
payload = create_binary_payload(data)

# Decode payload
decoded = decode_binary_payload(payload)
```

### CLI Usage

#### Encode JSON to Binary

```bash
# From JSON file, output as hex
python encode.py encode -i example_data.json

# From JSON file, output to binary file
python encode.py encode -i example_data.json -o payload.bin

# From stdin
echo '{"device_ip":"192.168.1.100","timestamp":1704067200,"distance":250,"state":"empty","success_rate":95,"baseline":300,"confidence":85}' | python encode.py encode
```

#### Decode Binary to JSON

```bash
# From binary file
python encode.py decode -i payload.bin

# From binary file with pretty printing
python encode.py decode -i payload.bin --pretty

# From hex string
python encode.py decode --hex c0a801646597e00000fa5f012c55

# Decode and save to file
python encode.py decode -i payload.bin -o decoded.json --pretty
```

#### Round-trip Example

```bash
# Encode -> Decode
python encode.py encode -i example_data.json | python encode.py decode --hex $(cat -)
```

## Running Tests

```bash
# Install pytest if needed
uv add --dev pytest

# Run tests
cd testing
pytest test_telemetry.py -v

# Or run directly
python test_telemetry.py
```

## Test Coverage

The test suite includes:

- ✓ All four state values (`empty`, `has_mail`, `full`, `emptied`)
- ✓ Boundary value testing (max/min values)
- ✓ Zero value testing
- ✓ Payload length validation
- ✓ Error handling (invalid payload sizes)
- ✓ Different IP addresses

## Example Payloads

### Empty Mailbox
```json
{
  "device_ip": "192.168.1.100",
  "timestamp": 1704067200,
  "distance": 250,
  "state": "empty",
  "success_rate": 95,
  "baseline": 300,
  "confidence": 85
}
```
Hex: `c0a801646597e00000fa5f012c55`

### Has Mail
```json
{
  "device_ip": "192.168.1.100",
  "timestamp": 1704067200,
  "distance": 180,
  "state": "has_mail",
  "success_rate": 98,
  "baseline": 290,
  "confidence": 92
}
```
Hex: `c0a801646597e0000b4016201225c`

### Full Mailbox
```json
{
  "device_ip": "192.168.1.100",
  "timestamp": 1704067200,
  "distance": 50,
  "state": "full",
  "success_rate": 100,
  "baseline": 310,
  "confidence": 99
}
```
Hex: `c0a801646597e000003202640136‌63`

## Integration with MQTT

### Using mosquitto.sh (Recommended)

The `../mosquitto.sh` script provides an easy way to publish binary telemetry to the MQTT broker:

```bash
# Interactive menu
./mosquitto.sh

# Direct command line usage
./mosquitto.sh collected  # Publish mail_collected event
./mosquitto.sh dropped    # Publish mail_dropped event
./mosquitto.sh status     # Publish status (has_mail)
./mosquitto.sh empty      # Publish status (empty)
./mosquitto.sh full       # Publish status (full)
./mosquitto.sh all        # Publish all events in sequence
```

The script automatically:
- Generates current unix timestamps
- Encodes JSON to binary using `encode.py`
- Converts hex to raw binary with `xxd`
- Publishes to MQTT broker via `mosquitto_pub -s` (stdin)

### Testing Locally

Use `test_publish.sh` to test payload generation without connecting to the broker:

```bash
cd testing
./test_publish.sh all      # Test all payload types
./test_publish.sh dropped  # Test specific payload type
```

This displays:
- The JSON input
- Hex-encoded payload
- Payload size (should be 15 bytes)
- Decoded verification

### Manual MQTT Publishing

For manual testing with mosquitto_pub:

```bash
# Encode and publish via stdin
echo '{"device_ip":"192.168.1.100","timestamp":1704067200,"distance":372,"state":"has_mail","success_rate":98,"baseline":400,"confidence":87}' | \
  python encode.py encode | xxd -r -p | \
  mosquitto_pub -h localhost -t "home/mailbox/status" -s

# Or encode to file and publish
python encode.py encode -i example_data.json -o payload.bin
mosquitto_pub -h localhost -t "home/mailbox/status" -f payload.bin
```

## Debugging Tips

1. **Verify payload length**: Should always be exactly 15 bytes
   ```bash
   python encode.py encode -i data.json -o test.bin && ls -l test.bin
   ```

2. **Inspect hex output**: Use hex output to manually verify encoding
   ```bash
   python encode.py encode -i data.json | xxd -r -p | xxd
   ```

3. **Round-trip validation**: Ensure encode->decode produces same data
   ```bash
   python encode.py encode -i data.json -o test.bin
   python encode.py decode -i test.bin --pretty
   ```
