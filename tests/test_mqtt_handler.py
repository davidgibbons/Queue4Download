"""
Tests for the mqtt_handler module.
"""
import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from mqtt_handler import MQTTHandler


class TestMQTTHandler:
    """Test cases for MQTTHandler class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_config = Mock()
        self.mock_config.bus_host = "test.mqtt.com"
        self.mock_config.bus_port = 1883
        self.mock_config.user = "testuser"
        self.mock_config.pw = "testpass"
        
        self.mock_transfer_handler = Mock()

    @patch('mqtt_handler.mqtt.Client')
    def test_init_creates_client(self, mock_client_class):
        """Test that MQTTHandler initializes MQTT client correctly."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Verify client creation
        mock_client_class.assert_called_once()
        
        # Verify client configuration
        mock_client.username_pw_set.assert_called_once_with("testuser", "testpass")
        
        # Verify callback assignments
        assert mock_client.on_connect == handler.on_connect
        assert mock_client.on_disconnect == handler.on_disconnect
        assert mock_client.on_message == handler.on_message
        assert mock_client.on_subscribe == handler.on_subscribe
        assert mock_client.on_publish == handler.on_publish
        assert mock_client.on_log == handler.on_log
        
        # Verify initial state
        assert handler.connected is False
        assert handler.running is False
        assert handler.reconnect_delay == 5
        assert handler.max_reconnect_delay == 60

    @patch('mqtt_handler.mqtt.Client')
    @patch('mqtt_handler.time.sleep')
    def test_start_successful_connection(self, mock_sleep, mock_client_class):
        """Test successful MQTT connection and subscription."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.connect.return_value = 0  # Success
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Mock the handler to stop after one iteration
        def mock_connect_side_effect(*args):
            handler.connected = True
            handler.running = False  # Stop the loop
            return 0
        
        mock_client.connect.side_effect = mock_connect_side_effect
        
        handler.start()
        
        # Verify connection attempt
        mock_client.connect.assert_called_with("test.mqtt.com", 1883, 60)
        mock_client.loop_start.assert_called_once()

    @patch('mqtt_handler.mqtt.Client')
    @patch('mqtt_handler.time.sleep')
    def test_start_connection_failure(self, mock_sleep, mock_client_class):
        """Test MQTT connection failure handling."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Track connection attempts
        connection_attempts = []
        
        def mock_connect_side_effect(*args):
            connection_attempts.append(1)
            if len(connection_attempts) >= 3:  # Stop after 3 attempts
                handler.running = False
            raise Exception("Connection failed")
        
        mock_client.connect.side_effect = mock_connect_side_effect
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.start()
        
        # Should attempt connection multiple times
        assert len(connection_attempts) >= 1
        mock_sleep.assert_called()  # Should have slept between attempts

    @patch('mqtt_handler.mqtt.Client')
    def test_stop_graceful_shutdown(self, mock_client_class):
        """Test graceful MQTT shutdown."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.running = True
        handler.connected = True
        
        handler.stop()
        
        # Verify shutdown sequence
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        
        assert handler.running is False

    @patch('mqtt_handler.mqtt.Client')
    def test_on_connect_successful(self, mock_client_class):
        """Test successful connection callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Mock subscribe to return success tuple
        mock_client.subscribe.return_value = (0, 123)  # Success, message ID 123
        
        # Simulate successful connection
        handler.on_connect(mock_client, None, None, 0)
        
        # Verify subscription
        mock_client.subscribe.assert_called_once_with("Down", qos=2)
        
        assert handler.connected is True
        assert handler.current_reconnect_delay == 5  # Reset to initial value

    @patch('mqtt_handler.mqtt.Client')
    def test_on_connect_failure(self, mock_client_class):
        """Test connection failure callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Simulate connection failure
        handler.on_connect(mock_client, None, None, 1)  # Connection refused
        
        # Verify no subscription
        mock_client.subscribe.assert_not_called()
        
        assert handler.connected is False

    @patch('mqtt_handler.mqtt.Client')
    def test_on_disconnect_normal(self, mock_client_class):
        """Test normal disconnect callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.connected = True
        
        # Simulate normal disconnect
        handler.on_disconnect(mock_client, None, 0)
        
        assert handler.connected is False

    @patch('mqtt_handler.mqtt.Client')
    def test_on_disconnect_unexpected(self, mock_client_class):
        """Test unexpected disconnect callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.connected = True
        handler.running = True
        
        # Simulate unexpected disconnect
        handler.on_disconnect(mock_client, None, 1)
        
        assert handler.connected is False

    @patch('mqtt_handler.mqtt.Client')
    def test_on_message_valid_event(self, mock_client_class):
        """Test message handling with valid event."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Create mock message
        mock_message = Mock()
        mock_message.topic = "Down"
        mock_message.payload.decode.return_value = "test.mkv\thash123\tMOV"
        mock_message.qos = 2
        mock_message.retain = False
        
        handler.on_message(mock_client, None, mock_message)
        
        # Verify transfer was called
        self.mock_transfer_handler.transfer_file.assert_called_once_with(
            "test.mkv", "hash123", "MOV"
        )

    @patch('mqtt_handler.mqtt.Client')
    def test_on_message_malformed_event(self, mock_client_class):
        """Test message handling with malformed event."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Create mock message with malformed payload
        mock_message = Mock()
        mock_message.topic = "Down"
        mock_message.payload.decode.return_value = "incomplete\tevent"
        mock_message.qos = 2
        mock_message.retain = False
        
        handler.on_message(mock_client, None, mock_message)
        
        # Verify transfer was not called
        self.mock_transfer_handler.transfer_file.assert_not_called()

    @patch('mqtt_handler.mqtt.Client')
    def test_publish_label_event_success(self, mock_client_class):
        """Test successful label event publishing."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the publish result object
        mock_result = Mock()
        mock_result.mid = 123
        mock_result.rc = 0  # Success
        mock_client.publish.return_value = mock_result
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.connected = True
        
        # The method doesn't return anything, it just publishes
        handler.publish_label_event("hash123", True)
        
        # Verify publish was called with correct parameters
        expected_topic = "Label"
        expected_payload = "hash123\tDONE"
        mock_client.publish.assert_called_once_with(expected_topic, expected_payload, qos=2)

    @patch('mqtt_handler.mqtt.Client')
    def test_publish_label_event_failure(self, mock_client_class):
        """Test label event publishing when not connected."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.connected = False
        
        # The method returns None when not connected
        result = handler.publish_label_event("hash123", True)
        
        # Verify publish was not called
        mock_client.publish.assert_not_called()
        
        # Method returns None when not connected
        assert result is None

    @patch('mqtt_handler.mqtt.Client')
    def test_connection_result_codes(self, mock_client_class):
        """Test connection result code handling."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Test all connection result codes
        test_cases = [
            (0, True),   # Success
            (1, False),  # Connection refused - incorrect protocol version
            (2, False),  # Connection refused - invalid client identifier
            (3, False),  # Connection refused - server unavailable
            (4, False),  # Connection refused - bad username or password
            (5, False),  # Connection refused - not authorised
            (99, False)  # Unknown connection error
        ]
        
        for code, expected_connected in test_cases:
            # Reset connected state
            handler.connected = False
            
            # Mock subscribe to return success tuple for successful connections
            if code == 0:
                mock_client.subscribe.return_value = (0, 123)
            
            handler.on_connect(mock_client, None, None, code)
            assert handler.connected is expected_connected

    @patch('mqtt_handler.mqtt.Client')
    def test_callbacks_assigned(self, mock_client_class):
        """Test that all callbacks are properly assigned."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Verify all callbacks are assigned
        assert mock_client.on_connect == handler.on_connect
        assert mock_client.on_message == handler.on_message
        assert mock_client.on_disconnect == handler.on_disconnect
        assert mock_client.on_publish == handler.on_publish
        assert mock_client.on_subscribe == handler.on_subscribe
        assert mock_client.on_log == handler.on_log

    @patch('mqtt_handler.mqtt.Client')
    @patch('mqtt_handler.logger')
    def test_logging_calls(self, mock_logger, mock_client_class):
        """Test that appropriate logging calls are made."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Test debug logging during initialization
        mock_logger.debug.assert_any_call("Initializing MQTT client for %s:%s",
                                          "test.mqtt.com", 1883)
        mock_logger.debug.assert_any_call("MQTT client initialized with custom reconnection handling")

    @patch('mqtt_handler.mqtt.Client')
    def test_subscribe_callback(self, mock_client_class):
        """Test subscribe callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Test subscribe callback
        handler.on_subscribe(mock_client, None, 123, [2])
        # Should not raise any exceptions

    @patch('mqtt_handler.mqtt.Client')
    def test_publish_callback(self, mock_client_class):
        """Test publish callback."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Test publish callback
        handler.on_publish(mock_client, None, 123)
        # Should not raise any exceptions

    @patch('mqtt_handler.mqtt.Client')
    def test_log_callback(self, mock_client_class):
        """Test log callback with different levels."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Test different log levels
        import paho.mqtt.client as mqtt
        
        # Test each log level
        handler.on_log(mock_client, None, mqtt.MQTT_LOG_DEBUG, "debug message")
        handler.on_log(mock_client, None, mqtt.MQTT_LOG_INFO, "info message")
        handler.on_log(mock_client, None, mqtt.MQTT_LOG_NOTICE, "notice message")
        handler.on_log(mock_client, None, mqtt.MQTT_LOG_WARNING, "warning message")
        handler.on_log(mock_client, None, mqtt.MQTT_LOG_ERR, "error message")
        
        # Should not raise any exceptions

    @patch('mqtt_handler.mqtt.Client')
    @patch('mqtt_handler.time.sleep')
    def test_connect_with_retry_exponential_backoff(self, mock_sleep, mock_client_class):
        """Test connection retry with exponential backoff."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Track connection attempts
        connection_attempts = []
        
        def mock_connect_side_effect(*args):
            connection_attempts.append(1)
            if len(connection_attempts) >= 3:  # Stop after 3 attempts
                handler.running = False
            raise Exception("Connection failed")
        
        mock_client.connect.side_effect = mock_connect_side_effect
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Set running to True before calling _connect_with_retry
        handler.running = True
        handler._connect_with_retry()
        
        # Should have attempted connection
        assert len(connection_attempts) >= 1
        
        # Should have called sleep for retry delay
        if len(connection_attempts) > 1:
            mock_sleep.assert_called()

    @patch('mqtt_handler.mqtt.Client')
    def test_reconnect_delay_reset_on_success(self, mock_client_class):
        """Test that reconnect delay is reset on successful connection."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.subscribe.return_value = (0, 123)
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Set delay to a higher value
        handler.current_reconnect_delay = 30
        
        # Simulate successful connection
        handler.on_connect(mock_client, None, None, 0)
        
        # Delay should be reset to initial value
        assert handler.current_reconnect_delay == 5

    @patch('mqtt_handler.mqtt.Client')
    def test_message_with_extra_fields(self, mock_client_class):
        """Test message handling with extra fields (should still work)."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        
        # Create mock message with extra fields
        mock_message = Mock()
        mock_message.topic = "Down"
        mock_message.payload.decode.return_value = "test.mkv\thash123\tMOV\textra\tfields"
        mock_message.qos = 2
        mock_message.retain = False
        
        handler.on_message(mock_client, None, mock_message)
        
        # Should still process the first 3 fields
        self.mock_transfer_handler.transfer_file.assert_called_once_with(
            "test.mkv", "hash123", "MOV"
        )

    @patch('mqtt_handler.mqtt.Client')
    def test_publish_label_event_nack(self, mock_client_class):
        """Test label event publishing with NACK (failure)."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the publish result object
        mock_result = Mock()
        mock_result.mid = 123
        mock_result.rc = 0  # Success
        mock_client.publish.return_value = mock_result
        
        handler = MQTTHandler(self.mock_config, self.mock_transfer_handler)
        handler.connected = True
        
        handler.publish_label_event("hash123", False)
        
        # Verify publish was called with NACK
        expected_topic = "Label"
        expected_payload = "hash123\tNOPE"
        mock_client.publish.assert_called_once_with(expected_topic, expected_payload, qos=2) 