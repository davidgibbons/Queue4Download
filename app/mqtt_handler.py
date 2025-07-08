"""
MQTT handler module for Q4D client.
Handles MQTT connections, subscriptions, and message processing with robust reconnection.
"""
import logging
import time
import paho.mqtt.client as mqtt  # pylint: disable=import-error

logger = logging.getLogger("MQTT")

# MQTT constants
ACK = "DONE"
NACK = "NOPE"
LABEL_CHANNEL = "Label"


class MQTTHandler:  # pylint: disable=too-many-instance-attributes
    """Handles MQTT connections and message processing with automatic reconnection."""

    def __init__(self, config, transfer_handler):
        """Initialize MQTT handler with configuration and transfer handler."""
        self.config = config
        self.transfer_handler = transfer_handler
        self.queue_channel = 'Down'
        self.connected = False
        self.running = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60  # seconds
        self.current_reconnect_delay = self.reconnect_delay

        logger.debug("Initializing MQTT client for %s:%s",
                     config.bus_host, config.bus_port)
        self.client = mqtt.Client()
        self.client.username_pw_set(self.config.user, self.config.pw)

        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe
        self.client.on_log = self.on_log

        # Disable automatic reconnection - we handle it ourselves
        # This prevents conflicts with our custom reconnection logic
        logger.debug("MQTT client initialized with custom reconnection handling")

    def start(self):
        """Start the MQTT client with automatic reconnection."""
        logger.info("Starting MQTT handler - connecting to %s:%s as %s",
                    self.config.bus_host, self.config.bus_port, self.config.user)
        logger.debug("Queue channel: %s", self.queue_channel)
        logger.debug("Label channel: %s", LABEL_CHANNEL)
        logger.debug("Reconnection settings - initial delay: %ds, max delay: %ds",
                     self.reconnect_delay, self.max_reconnect_delay)

        self.running = True
        self._connect_with_retry()

        # Start the network loop in a separate thread
        self.client.loop_start()
        logger.debug("MQTT network loop started")

        # Keep the main thread alive and handle reconnections
        try:
            while self.running:
                if not self.connected:
                    logger.warning("MQTT connection lost, attempting to reconnect...")
                    self._connect_with_retry()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down MQTT handler")
        finally:
            self.stop()

    def stop(self):
        """Stop the MQTT client gracefully."""
        logger.info("Stopping MQTT handler")
        self.running = False

        if self.client:
            self.client.loop_stop()
            if self.connected:
                self.client.disconnect()
                logger.debug("MQTT client disconnected")

        logger.info("MQTT handler stopped")

    def _connect_with_retry(self):
        """Connect to MQTT broker with exponential backoff retry logic."""
        while self.running and not self.connected:
            try:
                logger.debug("Attempting MQTT connection to %s:%s",
                             self.config.bus_host, self.config.bus_port)
                self.client.connect(self.config.bus_host, self.config.bus_port, 60)
                # Connection success will be handled in on_connect callback
                break

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to connect to MQTT broker: %s", e)
                logger.debug("Connection attempt failed, waiting %d seconds before retry",
                             self.current_reconnect_delay)

                # Wait before retrying
                time.sleep(self.current_reconnect_delay)

                # Exponential backoff
                self.current_reconnect_delay = min(self.current_reconnect_delay * 2,
                                                   self.max_reconnect_delay)
                logger.debug("Next reconnect delay: %d seconds", self.current_reconnect_delay)

    def on_connect(self, _client, _userdata, flags, rc):
        """Callback for when the client connects to the MQTT broker."""
        if rc == 0:
            self.connected = True
            # Reset delay on successful connection
            self.current_reconnect_delay = self.reconnect_delay
            logger.info("Connected to MQTT broker. Subscribing to %s", self.queue_channel)
            logger.debug("Connection flags: %s", flags)

            # Subscribe to the queue channel
            result, mid = _client.subscribe(self.queue_channel, qos=2)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.debug("Subscription request sent for %s (message ID: %d)",
                             self.queue_channel, mid)
            else:
                logger.error("Failed to subscribe to %s, error code: %d",
                             self.queue_channel, result)

        else:
            self.connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            logger.error("Failed to connect to MQTT broker: %s", error_msg)

    def on_disconnect(self, _client, _userdata, rc):
        """Callback for when the client disconnects from the MQTT broker."""
        self.connected = False

        if rc == 0:
            logger.info("MQTT client disconnected normally")
        else:
            disconnect_reasons = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorised",
                6: "Unexpected disconnect",
                7: "No more retries"
            }
            reason = disconnect_reasons.get(rc, f"Unknown disconnect reason: {rc}")
            logger.warning("Unexpected MQTT disconnection: %s (code: %d)", reason, rc)

            if self.running:
                logger.info("Will attempt to reconnect...")

    def on_subscribe(self, _client, _userdata, mid, granted_qos):
        """Callback for when the client receives a SUBACK response from the server."""
        logger.debug("Subscribed successfully (message ID: %d, QoS: %s)", mid, granted_qos)

    def on_publish(self, _client, _userdata, mid):
        """Callback for when a message is published."""
        logger.debug("Message published successfully (message ID: %d)", mid)

    def on_log(self, _client, _userdata, level, buf):
        """Callback for MQTT client logging."""
        # Only log MQTT client messages at debug level to avoid spam
        if level == mqtt.MQTT_LOG_DEBUG:
            logger.debug("MQTT client debug: %s", buf)
        elif level == mqtt.MQTT_LOG_INFO:
            logger.debug("MQTT client info: %s", buf)
        elif level == mqtt.MQTT_LOG_NOTICE:
            logger.info("MQTT client notice: %s", buf)
        elif level == mqtt.MQTT_LOG_WARNING:
            logger.warning("MQTT client warning: %s", buf)
        elif level == mqtt.MQTT_LOG_ERR:
            logger.error("MQTT client error: %s", buf)

    def on_message(self, _client, _userdata, msg):
        """Callback for when a message is received from the MQTT broker."""
        event_str = msg.payload.decode()
        logger.info("Event received: %s", event_str)
        logger.debug("Message topic: %s, QoS: %d, retain: %s",
                     msg.topic, msg.qos, msg.retain)

        event = event_str.split('\t')
        if len(event) < 3:
            logger.error("Malformed event: %s", event_str)
            logger.debug("Expected at least 3 fields, got %d: %s", len(event), event)
            return

        filename, hash_, typecode = event[:3]
        logger.debug("Parsed event - filename: %s, hash: %s, typecode: %s",
                     filename, hash_, typecode)

        if len(event) > 3:
            logger.debug("Additional event fields ignored: %s", event[3:])

        logger.debug("Starting file transfer")
        success = self.transfer_handler.transfer_file(filename, hash_, typecode)
        logger.debug("Transfer completed with success: %s", success)

        if self.config.labelling and hash_ != "NotUsed":
            logger.debug("Labelling enabled and hash is not 'NotUsed', publishing label event")
            self.publish_label_event(hash_, success)
        else:
            logger.debug("Skipping label event - labelling: %s, hash: %s",
                         self.config.labelling, hash_)

    def publish_label_event(self, hash_, success):
        """Publish a label event to indicate transfer success or failure."""
        if not self.connected:
            logger.warning("Cannot publish label event - MQTT not connected")
            return

        label = ACK if success else NACK
        event = f"{hash_}\t{label}"
        logger.info("Publishing label event: %s to %s", event, LABEL_CHANNEL)
        logger.debug("Label event details - hash: %s, success: %s, label: %s",
                     hash_, success, label)

        try:
            result = self.client.publish(LABEL_CHANNEL, event, qos=2)
            logger.debug("Publish result - message ID: %d, return code: %d",
                         result.mid, result.rc)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug("Label event queued for publishing")
            else:
                logger.warning("Failed to publish label event, return code: %d", result.rc)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Exception while publishing label event: %s", e)
            logger.debug("Publish exception details:", exc_info=True)
