collected='{"device_ip":"192.168.1.100","timestamp":"26.11.2025 19:11:25","before_cm":37.2,"after_cm":39.8,"baseline_cm":40,"duration_ms":280,"success_rate":0.97,"new_state":"emptied"}'
dropped='{"device_ip":"192.168.1.100","timestamp":"26.11.2025 19:11:25","distance_cm":37.2,"baseline_cm":40,"duration_ms":485,"confidence":0.87,"success_rate":0.98,"new_state":"has_mail"}'
telemetry='{"device_ip":"192.168.1.100","timestamp":"26.11.2025 19:11:25","distance_cm":37.3,"baseline_cm":40,"threshold_cm":38,"success_rate":0.98,"mailbox_state":"has_mail"}'



publish_collected() {
    mosquitto_pub \
        -h mailbox.oci.heofthetea.me \
        -i test_pub \
        -t "home/mailbox/events/mail_collected" \
        -q 1 \
        -m "$collected"
}
publish_dropped() {
    mosquitto_pub \
        -h mailbox.oci.heofthetea.me \
        -i test_pub \
        -t "home/mailbox/events/mail_dropped" \
        -q 1 \
        -m "$dropped"
}
publish_telemetry() {
    mosquitto_pub \
        -h mailbox.oci.heofthetea.me \
        -i test_pub \
        -t "home/mailbox/status" \
        -q 1 \
        -m "$telemetry"
}
