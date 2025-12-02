#!/usr/bin/env python3
"""
Binary payload encoder for MVP telemetry protocol.

This module provides utilities to encode telemetry data into the binary
protocol format used by the ESP mailbox devices.

Binary Protocol Format (Big Endian):
- ip: u32 (4 bytes)
- timestamp: u32 (4 bytes, unix timestamp)
- distance: u16 (2 bytes)
- state: u8 (1 byte, 3 bits used)
- success_rate: u8 (1 byte)
- baseline: u16 (2 bytes)
- confidence: u8 (1 byte)

Total: 15 bytes
"""

import struct
import json
import sys
import argparse


def ip_to_u32(ip_str: str) -> int:
    """
    Convert IP address string to u32 integer.

    Args:
        ip_str: IP address in dotted decimal notation (e.g., "192.168.1.100")

    Returns:
        32-bit unsigned integer representation

    Example:
        >>> ip_to_u32("192.168.1.100")
        3232235876
    """
    parts = ip_str.split('.')
    if len(parts) != 4:
        raise ValueError(f"Invalid IP address format: {ip_str}")

    for part in parts:
        if not 0 <= int(part) <= 255:
            raise ValueError(f"Invalid IP address octet: {part}")

    return (int(parts[0]) << 24) | (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])


def u32_to_ip(ip_int: int) -> str:
    """
    Convert u32 integer to IP address string.

    Args:
        ip_int: 32-bit unsigned integer

    Returns:
        IP address in dotted decimal notation

    Example:
        >>> u32_to_ip(3232235876)
        "192.168.1.100"
    """
    return f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"


def state_to_u8(state: str) -> int:
    """
    Convert state string to u8 integer.

    Args:
        state: One of "empty", "has_mail", "full", "emptied"

    Returns:
        Numeric state value (0-3)

    Raises:
        ValueError: If state is not recognized
    """
    state_map = {
        "empty": 0,
        "has_mail": 1,
        "full": 2,
        "emptied": 3
    }

    if state not in state_map:
        raise ValueError(f"Invalid state: {state}. Must be one of {list(state_map.keys())}")

    return state_map[state]


def u8_to_state(state_int: int) -> str:
    """
    Convert u8 integer to state string.

    Args:
        state_int: Numeric state value (0-3)

    Returns:
        State string

    Raises:
        ValueError: If state_int is out of range
    """
    state_map = {
        0: "empty",
        1: "has_mail",
        2: "full",
        3: "emptied"
    }

    if state_int not in state_map:
        raise ValueError(f"Invalid state value: {state_int}. Must be 0-3")

    return state_map[state_int]


def create_binary_payload(data: dict) -> bytes:
    """
    Create binary payload from dictionary according to protocol specification.

    Args:
        data: Dictionary containing:
            - device_ip (str): IP address
            - timestamp (int): Unix timestamp
            - distance (int): Distance in mm (0-65535)
            - state (str): One of "empty", "has_mail", "full", "emptied"
            - success_rate (int): Success rate 0-255
            - baseline (int): Baseline distance 0-65535
            - confidence (int): Confidence level 0-255

    Returns:
        15-byte binary payload in big-endian format

    Raises:
        KeyError: If required field is missing
        ValueError: If field value is invalid or out of range

    Example:
        >>> data = {
        ...     "device_ip": "192.168.1.100",
        ...     "timestamp": 1704067200,
        ...     "distance": 250,
        ...     "state": "empty",
        ...     "success_rate": 95,
        ...     "baseline": 300,
        ...     "confidence": 85
        ... }
        >>> payload = create_binary_payload(data)
        >>> len(payload)
        15
    """
    # Validate and convert fields
    try:
        ip_u32 = ip_to_u32(data["device_ip"])
    except KeyError:
        raise KeyError("Missing required field: device_ip")

    try:
        timestamp_u32 = int(data["timestamp"])
        if not 0 <= timestamp_u32 <= 0xFFFFFFFF:
            raise ValueError(f"timestamp out of range: {timestamp_u32}")
    except KeyError:
        raise KeyError("Missing required field: timestamp")

    try:
        distance_u16 = int(data["distance"])
        if not 0 <= distance_u16 <= 0xFFFF:
            raise ValueError(f"distance out of range: {distance_u16}")
    except KeyError:
        raise KeyError("Missing required field: distance")

    try:
        state_u8 = state_to_u8(data["state"])
    except KeyError:
        raise KeyError("Missing required field: state")

    try:
        success_rate_u8 = int(data["success_rate"])
        if not 0 <= success_rate_u8 <= 0xFF:
            raise ValueError(f"success_rate out of range: {success_rate_u8}")
    except KeyError:
        raise KeyError("Missing required field: success_rate")

    try:
        baseline_u16 = int(data["baseline"])
        if not 0 <= baseline_u16 <= 0xFFFF:
            raise ValueError(f"baseline out of range: {baseline_u16}")
    except KeyError:
        raise KeyError("Missing required field: baseline")

    try:
        confidence_u8 = int(data["confidence"])
        if not 0 <= confidence_u8 <= 0xFF:
            raise ValueError(f"confidence out of range: {confidence_u8}")
    except KeyError:
        raise KeyError("Missing required field: confidence")

    # Pack as big-endian: I=u32, H=u16, B=u8
    payload = struct.pack(
        '>IIHBBHB',
        ip_u32,
        timestamp_u32,
        distance_u16,
        state_u8,
        success_rate_u8,
        baseline_u16,
        confidence_u8
    )

    return payload


def decode_binary_payload(payload: bytes) -> dict:
    """
    Decode binary payload back to dictionary format.

    Args:
        payload: 15-byte binary payload in big-endian format

    Returns:
        Dictionary with decoded fields

    Raises:
        struct.error: If payload is wrong size

    Example:
        >>> payload = b'\\xc0\\xa8\\x01d\\x65\\x9f\\x00\\x00\\x00\\xfa\\x00_\\x01,\\x55'
        >>> data = decode_binary_payload(payload)
        >>> data['device_ip']
        '192.168.1.100'
    """
    if len(payload) != 15:
        raise ValueError(f"Invalid payload length: {len(payload)} (expected 15)")

    # Unpack as big-endian
    ip_u32, timestamp_u32, distance_u16, state_u8, success_rate_u8, baseline_u16, confidence_u8 = struct.unpack(
        '>IIHBBHB',
        payload
    )

    return {
        "device_ip": u32_to_ip(ip_u32),
        "timestamp": timestamp_u32,
        "distance": distance_u16,
        "state": u8_to_state(state_u8),
        "success_rate": success_rate_u8,
        "baseline": baseline_u16,
        "confidence": confidence_u8
    }


def main():
    """CLI interface for encoding/decoding binary payloads."""
    parser = argparse.ArgumentParser(
        description="Encode/decode MQTT Mailbox telemetry binary payloads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encode from JSON file
  python encode.py encode -i data.json -o payload.bin

  # Encode from stdin
  echo '{"device_ip":"192.168.1.100","timestamp":1704067200,"distance":250,"state":"empty","success_rate":95,"baseline":300,"confidence":85}' | python encode.py encode

  # Decode binary file
  python encode.py decode -i payload.bin

  # Decode hex string
  python encode.py decode --hex c0a801646000000000fa005f012c55
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Encode command
    encode_parser = subparsers.add_parser('encode', help='Encode JSON to binary payload')
    encode_parser.add_argument('-i', '--input', help='Input JSON file (default: stdin)')
    encode_parser.add_argument('-o', '--output', help='Output binary file (default: stdout as hex)')
    encode_parser.add_argument('--hex', action='store_true', help='Output as hex string instead of binary')

    # Decode command
    decode_parser = subparsers.add_parser('decode', help='Decode binary payload to JSON')
    decode_parser.add_argument('-i', '--input', help='Input binary file (default: stdin)')
    decode_parser.add_argument('-o', '--output', help='Output JSON file (default: stdout)')
    decode_parser.add_argument('--hex', help='Decode from hex string instead of file')
    decode_parser.add_argument('--pretty', action='store_true', help='Pretty-print JSON output')
    decode_parser.add_argument('--stream', action='store_true', help='Stream mode: continuously read 15-byte messages from stdin')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'encode':
            # Read JSON input
            if args.input:
                with open(args.input, 'r') as f:
                    data = json.load(f)
            else:
                data = json.load(sys.stdin)

            # Create binary payload
            payload = create_binary_payload(data)

            # Write output
            if args.output:
                with open(args.output, 'wb') as f:
                    f.write(payload)
                print(f"✓ Encoded {len(payload)} bytes to {args.output}", file=sys.stderr)
            else:
                # Output as hex to stdout
                hex_str = payload.hex()
                print(hex_str)

        elif args.command == 'decode':
            # Stream mode: continuously read 15-byte chunks
            # Note: mosquitto_sub adds newlines between messages, so we need to handle them
            if args.stream:
                message_count = 0
                while True:
                    # Read exactly 15 bytes for the payload
                    payload = sys.stdin.buffer.read(15)

                    # Exit if no more data
                    if len(payload) == 0:
                        break

                    # Warn if incomplete message
                    if len(payload) != 15:
                        print(f"Warning: Incomplete message ({len(payload)} bytes, expected 15)", file=sys.stderr)
                        print(f"Hex dump: {payload.hex()}", file=sys.stderr)
                        break

                    try:
                        # Decode payload
                        data = decode_binary_payload(payload)
                        message_count += 1

                        print(json.dumps(data, indent=2 if args.pretty else None))
                        sys.stdout.flush()  # Ensure immediate output
                        
                        # mosquitto_sub adds a newline after each message - consume it
                        newline = sys.stdin.buffer.read(1)
                        if newline and newline != b'\n':
                            # If it's not a newline, we're misaligned - print warning
                            print(f"Warning: Expected newline after message #{message_count}, got: {newline.hex()}", file=sys.stderr)
                            
                    except Exception as e:
                        print(f"Error decoding message #{message_count + 1}: {e}", file=sys.stderr)
                        print(f"Hex dump of failed payload: {payload.hex()}", file=sys.stderr)
                        # Try to recover by reading until we find something that looks like an IP
                        # This is a simple heuristic - real recovery would need message framing
                        break

            # Single message mode
            else:
                # Read binary input
                if args.hex:
                    payload = bytes.fromhex(args.hex)
                elif args.input:
                    with open(args.input, 'rb') as f:
                        payload = f.read()
                else:
                    payload = sys.stdin.buffer.read()

                # Decode payload
                data = decode_binary_payload(payload)

                # Write output
                if args.output:
                    with open(args.output, 'w') as f:
                        json.dump(data, f, indent=2 if args.pretty else None)
                    print(f"✓ Decoded to {args.output}", file=sys.stderr)
                else:
                    print(json.dumps(data, indent=2 if args.pretty else None))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit(0)
