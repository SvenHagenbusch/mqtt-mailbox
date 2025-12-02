# Testing Utilities

This directory contains testing utilities for the MQTT Mailbox binary protocol.

> DISCLAIMER: All testing is completely vibe-coded and I have absolutely zero fucking idea how any of it works

## MVP Format

The mailbox-vibe protocol uses **big-endian** byte order with the following structure (15 bytes total):

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


## Receive MVP messages and immediately decode them
```bash
mosquitto_sub -h mailbox.oci.heofthetea.me -i test_sub -t "home/mailbox/#" | python3 encode.py decode --stream 
```

> **hint**: This outputs compact JSON -> use JQ to prettify it. 

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

### Subscribing and Decoding with mosquitto_sub

The `encode.py` decode command supports **streaming mode** for continuous processing of MQTT messages.

#### Simple Piping with mosquitto_decode.sh (Easiest)

```bash
# Continuous streaming with automatic decoding
mosquitto_sub -h localhost -t "home/mailbox/#" | ./mosquitto_decode.sh

# With pretty-printing
mosquitto_sub -h localhost -t "home/mailbox/#" | ./mosquitto_decode.sh --pretty

# Specific topic
mosquitto_sub -h localhost -t "home/mailbox/status" | ./mosquitto_decode.sh --pretty
```

The `mosquitto_decode.sh` wrapper automatically uses streaming mode to read 15-byte messages continuously.

#### Direct Usage with encode.py --stream

```bash
# Stream mode: reads 15 bytes at a time, outputs JSON for each message
mosquitto_sub -h localhost -t "home/mailbox/#" | python3 encode.py decode --stream

# With pretty printing
mosquitto_sub -h localhost -t "home/mailbox/#" | python3 encode.py decode --stream --pretty

# Monitor only events
mosquitto_sub -h localhost -t "home/mailbox/events/#" | python3 encode.py decode --stream --pretty
```

**How it works:**
- `mosquitto_sub` outputs raw binary (15 bytes per message)
- `encode.py --stream` reads exactly 15 bytes at a time
- Each message is decoded and output immediately
- Process continues until Ctrl+C or connection closes

#### Example Output

```bash
$ mosquitto_sub -h localhost -t "home/mailbox/#" | python3 encode.py decode --stream --pretty
--- Message #1 ---
{
  "device_ip": "192.168.1.100",
  "timestamp": 1704067200,
  "distance": 250,
  "state": "empty",
  "success_rate": 95,
  "baseline": 300,
  "confidence": 85
}
--- Message #2 ---
{
  "device_ip": "192.168.1.100",
  "timestamp": 1704067212,
  "distance": 372,
  "state": "has_mail",
  "success_rate": 98,
  "baseline": 400,
  "confidence": 87
}
```

#### Converting to Hex First (Alternative Method)

If you need to see the hex representation:

```bash
# Using xxd -p for plain hex output (removes spaces/newlines with tr)
mosquitto_sub -h localhost -t "home/mailbox/status" -C 1 | xxd -p | tr -d '\n' | \
  xargs python3 encode.py decode --hex

# Note: This only works for single messages due to the way hex concatenates
```

For continuous hex monitoring, use `mosquitto_sub -F "%p"` format:

```bash
mosquitto_sub -h localhost -t "home/mailbox/#" -F "%p" | \
  while read hex; do
    python3 encode.py decode --hex "$hex" --pretty
  done
```

#### Using with jq for Filtering

```bash
# Filter only "has_mail" states
mosquitto_sub -h localhost -t "home/mailbox/#" | \
  python3 encode.py decode --stream | \
  jq 'select(.state == "has_mail")'

# Extract specific fields
mosquitto_sub -h localhost -t "home/mailbox/#" | \
  python3 encode.py decode --stream | \
  jq '{ip: .device_ip, state: .state, distance: .distance}'

# Log to file
mosquitto_sub -h localhost -t "home/mailbox/#" | \
  python3 encode.py decode --stream >> mqtt_messages.jsonl
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

4. **Test streaming decode**: Simulate multiple messages
   ```bash
   # Generate two messages and stream them
   (python3 encode.py encode -i example_data.json | xxd -r -p; \
    python3 encode.py encode -i example_data.json | xxd -r -p) | \
    python3 encode.py decode --stream --pretty
   ```

5. **Verify mosquitto_sub output**: Check raw binary is 15 bytes
   ```bash
   mosquitto_sub -h localhost -t "home/mailbox/status" -C 1 | wc -c
   # Should output: 15
   ```

6. **Debug streaming issues**: Add message count
   ```bash
   mosquitto_sub -h localhost -t "home/mailbox/#" | \
     python3 encode.py decode --stream 2>&1 | \
     grep -E "(Message|Error)"
   ```
