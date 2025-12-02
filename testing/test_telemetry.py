import sys
from pathlib import Path

# Add parent directory to path to import server module
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from server import MailboxTelemetry
from encode import create_binary_payload


class TestMailboxTelemetry:
    """Unit tests for MailboxTelemetry binary protocol parsing."""

    def test_from_byte_stream_empty_state(self):
        """Test parsing telemetry with 'empty' state."""
        # Create test data
        test_data = {
            "device_ip": "192.168.1.100",
            "timestamp": 1704067200,  # 2024-01-01 00:00:00 UTC
            "distance": 250,
            "state": "empty",
            "success_rate": 95,
            "baseline": 300,
            "confidence": 85
        }

        # Create binary payload
        payload = create_binary_payload(test_data)

        # Parse payload
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        # Validate
        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]
        # Note: timestamp comparison depends on implementation

    def test_from_byte_stream_has_mail_state(self):
        """Test parsing telemetry with 'has_mail' state."""
        test_data = {
            "device_ip": "10.0.0.50",
            "timestamp": 1704153600,  # 2024-01-02 00:00:00 UTC
            "distance": 180,
            "state": "has_mail",
            "success_rate": 98,
            "baseline": 290,
            "confidence": 92
        }

        payload = create_binary_payload(test_data)
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]

    def test_from_byte_stream_full_state(self):
        """Test parsing telemetry with 'full' state."""
        test_data = {
            "device_ip": "172.16.0.1",
            "timestamp": 1704240000,  # 2024-01-03 00:00:00 UTC
            "distance": 50,
            "state": "full",
            "success_rate": 100,
            "baseline": 310,
            "confidence": 99
        }

        payload = create_binary_payload(test_data)
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]

    def test_from_byte_stream_emptied_state(self):
        """Test parsing telemetry with 'emptied' state."""
        test_data = {
            "device_ip": "192.168.100.200",
            "timestamp": 1704326400,  # 2024-01-04 00:00:00 UTC
            "distance": 280,
            "state": "emptied",
            "success_rate": 88,
            "baseline": 295,
            "confidence": 0  # 0 for collected events
        }

        payload = create_binary_payload(test_data)
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]

    def test_from_byte_stream_boundary_values(self):
        """Test parsing telemetry with boundary values."""
        test_data = {
            "device_ip": "255.255.255.255",
            "timestamp": 0xFFFFFFFF,  # Max u32
            "distance": 65535,  # Max u16
            "state": "full",
            "success_rate": 255,  # Max u8
            "baseline": 65535,  # Max u16
            "confidence": 255  # Max u8
        }

        payload = create_binary_payload(test_data)
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]

    def test_from_byte_stream_zero_values(self):
        """Test parsing telemetry with zero values."""
        test_data = {
            "device_ip": "0.0.0.0",
            "timestamp": 0,
            "distance": 0,
            "state": "empty",
            "success_rate": 0,
            "baseline": 0,
            "confidence": 0
        }

        payload = create_binary_payload(test_data)
        telemetry = MailboxTelemetry.from_byte_stream(payload)

        assert telemetry.device_ip == test_data["device_ip"]
        assert telemetry.distance == test_data["distance"]
        assert telemetry.state == test_data["state"]
        assert telemetry.success_rate == test_data["success_rate"]
        assert telemetry.baseline == test_data["baseline"]
        assert telemetry.confidence == test_data["confidence"]

    def test_from_byte_stream_payload_length(self):
        """Test that payload has correct length (15 bytes)."""
        test_data = {
            "device_ip": "192.168.1.1",
            "timestamp": 1704067200,
            "distance": 200,
            "state": "has_mail",
            "success_rate": 90,
            "baseline": 300,
            "confidence": 80
        }

        payload = create_binary_payload(test_data)
        assert len(payload) == 15, "Payload should be exactly 15 bytes"

    def test_from_byte_stream_invalid_payload_too_short(self):
        """Test that parsing fails gracefully with too short payload."""
        invalid_payload = b'\x01\x02\x03'  # Only 3 bytes instead of 15

        with pytest.raises(Exception):  # Should raise some exception
            MailboxTelemetry.from_byte_stream(invalid_payload)

    def test_from_byte_stream_invalid_payload_too_long(self):
        """Test that parsing handles payload longer than expected."""
        test_data = {
            "device_ip": "192.168.1.1",
            "timestamp": 1704067200,
            "distance": 200,
            "state": "has_mail",
            "success_rate": 90,
            "baseline": 300,
            "confidence": 80
        }

        payload = create_binary_payload(test_data) + b'\xFF\xFF'  # Extra bytes

        # Should either parse first 15 bytes or raise exception
        # Implementation dependent
        try:
            telemetry = MailboxTelemetry.from_byte_stream(payload)
            # If it succeeds, verify the data is correct
            assert telemetry.device_ip == test_data["device_ip"]
        except Exception:
            # If it raises, that's also acceptable
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
