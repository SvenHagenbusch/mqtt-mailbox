#!/bin/bash

# MQTT Mailbox Testing Script
# Uses binary protocol for telemetry data

BROKER="mailbox.oci.heofthetea.me"
CLIENT_ID="test_pub"
QOS=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENCODE_SCRIPT="$SCRIPT_DIR/mvp.py"

# Helper function to get current unix timestamp
get_timestamp() {
    date +%s
}

# Helper function to encode JSON and publish
# Args: $1=topic, $2=json_data
publish_binary() {
    local topic="$1"
    local json_data="$2"

    # Encode JSON to binary hex, convert to binary, and publish
    echo "$json_data" | python3 "$ENCODE_SCRIPT" encode | xxd -r -p | \
        mosquitto_pub \
            -h "$BROKER" \
            -i "$CLIENT_ID" \
            -t "$topic" \
            -q "$QOS" \
            -s

    if [ $? -eq 0 ]; then
        echo "✓ Published to $topic"
    else
        echo "✗ Failed to publish to $topic" >&2
        return 1
    fi
}

# Publish mail collected event
publish_collected() {
    local timestamp=$(get_timestamp)

    # State: "emptied" after mail collection
    # Confidence: 0 for collected events
    # Distance: after collection (increased distance)
    local json=$(cat <<EOF
{
    "device_ip": "192.168.1.100",
    "timestamp": $timestamp,
    "distance": 398,
    "state": "emptied",
    "success_rate": 97,
    "baseline": 400,
    "confidence": 0
}
EOF
)

    publish_binary "home/mailbox/events/mail_collected" "$json"
}

# Publish mail drop event
publish_dropped() {
    local timestamp=$(get_timestamp)

    # State: "has_mail" after drop
    # Higher confidence for drop detection
    # Distance: decreased due to mail presence
    local json=$(cat <<EOF
{
    "device_ip": "192.168.1.100",
    "timestamp": $timestamp,
    "distance": 372,
    "state": "has_mail",
    "success_rate": 98,
    "baseline": 400,
    "confidence": 87
}
EOF
)

    publish_binary "home/mailbox/events/mail_dropped" "$json"
}

# Publish status/telemetry
publish_status() {
    local timestamp=$(get_timestamp)

    # Regular status update
    # Confidence: 0 for status messages
    local json=$(cat <<EOF
{
    "device_ip": "192.168.1.100",
    "timestamp": $timestamp,
    "distance": 373,
    "state": "empty",
    "success_rate": 98,
    "baseline": 400,
    "confidence": 0
}
EOF
)

    publish_binary "home/mailbox/status" "$json"
}

# Publish empty state
publish_empty() {
    local timestamp=$(get_timestamp)

    local json=$(cat <<EOF
{
    "device_ip": "192.168.1.100",
    "timestamp": $timestamp,
    "distance": 395,
    "state": "empty",
    "success_rate": 95,
    "baseline": 400,
    "confidence": 0
}
EOF
)

    publish_binary "home/mailbox/status" "$json"
}

# Publish full state
publish_full() {
    local timestamp=$(get_timestamp)

    local json=$(cat <<EOF
{
    "device_ip": "192.168.1.100",
    "timestamp": $timestamp,
    "distance": 50,
    "state": "full",
    "success_rate": 100,
    "baseline": 400,
    "confidence": 0
}
EOF
)

    publish_binary "home/mailbox/status" "$json"
}

# Main menu
show_menu() {
    echo ""
    echo "MQTT Mailbox Test Publisher (Binary Protocol)"
    echo "=============================================="
    echo "1) Publish mail_collected event"
    echo "2) Publish mail_dropped event"
    echo "3) Publish status (has_mail)"
    echo "4) Publish status (empty)"
    echo "5) Publish status (full)"
    echo "6) Publish all events"
    echo "q) Quit"
    echo ""
}

# Publish all for testing
publish_all() {
    echo "Publishing all events..."
    publish_empty
    sleep 1
    publish_dropped
    sleep 1
    publish_status
    sleep 1
    publish_collected
    sleep 1
    publish_empty
    echo "✓ All events published"
}

# Main loop
main() {
    # Check if encode.py exists
    if [ ! -f "$ENCODE_SCRIPT" ]; then
        echo "Error: encode.py not found at $ENCODE_SCRIPT" >&2
        exit 1
    fi

    # Check if mosquitto_pub is available
    if ! command -v mosquitto_pub &> /dev/null; then
        echo "Error: mosquitto_pub not found. Please install mosquitto-clients" >&2
        exit 1
    fi

    # If arguments provided, run directly
    case "$1" in
        collected|collect)
            publish_collected
            exit 0
            ;;
        dropped|drop)
            publish_dropped
            exit 0
            ;;
        status|telemetry)
            publish_status
            exit 0
            ;;
        empty)
            publish_empty
            exit 0
            ;;
        full)
            publish_full
            exit 0
            ;;
        all)
            publish_all
            exit 0
            ;;
    esac

    # Interactive menu
    while true; do
        show_menu
        read -p "Select option: " choice

        case "$choice" in
            1)
                publish_collected
                ;;
            2)
                publish_dropped
                ;;
            3)
                publish_status
                ;;
            4)
                publish_empty
                ;;
            5)
                publish_full
                ;;
            6)
                publish_all
                ;;
            q|Q)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo "Invalid option"
                ;;
        esac
    done
}

main "$@"
