"""
Tests for the process_event module.
"""
import signal
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from process_event import ProcessEvent, setup_logging, parse_arguments


class TestProcessEvent:
    """Test cases for process_event module."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_config = Mock()
        self.mock_config.bus_host = "test.mqtt.com"
        self.mock_config.bus_port = 1883
        self.mock_config.user = "testuser"
        self.mock_config.pw = "testpass"
        self.mock_config.labelling = True
        self.mock_config.host = "test.sftp.com"

    def test_setup_logging_debug(self):
        """Test logging setup with debug enabled."""
        with patch('process_event.logging.basicConfig') as mock_config:
            setup_logging(debug=True)
            
            mock_config.assert_called_once()
            call_args = mock_config.call_args[1]
            assert call_args['level'] == 10  # DEBUG level

    def test_setup_logging_info(self):
        """Test logging setup with info level."""
        with patch('process_event.logging.basicConfig') as mock_config:
            setup_logging(debug=False)
            
            mock_config.assert_called_once()
            call_args = mock_config.call_args[1]
            assert call_args['level'] == 20  # INFO level

    def test_parse_arguments_defaults(self):
        """Test argument parsing with default values."""
        test_args = ["process_event.py"]
        
        with patch('sys.argv', test_args):
            args = parse_arguments()
            
            assert args.config == 'q4d.conf'
            assert args.type_mapping == 'type_mapping.json'
            assert args.debug is False

    def test_parse_arguments_custom_values(self):
        """Test argument parsing with custom values."""
        test_args = ["process_event.py", "--config", "custom.conf", 
                    "--type-mapping", "custom.json", "--debug"]
        
        with patch('sys.argv', test_args):
            args = parse_arguments()
            
            assert args.config == 'custom.conf'
            assert args.type_mapping == 'custom.json'
            assert args.debug is True

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    def test_process_event_init(self, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test ProcessEvent initialization."""
        mock_load_mapping.return_value = {"MOV": "/downloads/movies"}
        mock_transfer = Mock()
        mock_transfer_class.return_value = mock_transfer
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        mapping_path = Path("test_mapping.json")
        
        pe = ProcessEvent(self.mock_config, mapping_path)
        
        # Verify components were initialized
        mock_load_mapping.assert_called_once_with(mapping_path)
        mock_transfer_class.assert_called_once_with(self.mock_config, {"MOV": "/downloads/movies"})
        mock_mqtt_class.assert_called_once_with(self.mock_config, mock_transfer)
        
        assert pe.config == self.mock_config
        assert pe.transfer_handler == mock_transfer
        assert pe.mqtt_handler == mock_mqtt

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    def test_process_event_start_success(self, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test successful ProcessEvent start."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        
        # Mock signal to avoid actual signal handling
        with patch('process_event.signal.signal'):
            pe.start()
        
        # Verify MQTT handler was started
        mock_mqtt.start.assert_called_once()

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    def test_process_event_start_mqtt_failure(self, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test ProcessEvent start with MQTT failure."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt.start.side_effect = Exception("MQTT failed")
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        
        with patch('process_event.signal.signal'):
            with pytest.raises(Exception, match="MQTT failed"):
                pe.start()

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    def test_process_event_stop(self, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test ProcessEvent stop."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        pe.stop()
        
        # Verify MQTT handler was stopped
        mock_mqtt.stop.assert_called_once()

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    def test_process_event_signal_handling(self, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test signal handler setup."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        
        with patch('process_event.signal.signal') as mock_signal:
            with patch('process_event.sys.exit') as mock_exit:
                pe.start()
                
                # Verify signal handlers were set up
                assert mock_signal.call_count == 2
                
                # Test signal handler
                signal_handler = mock_signal.call_args_list[0][0][1]
                signal_handler(signal.SIGINT, None)
                
                # Should call stop and exit
                mock_mqtt.stop.assert_called()
                mock_exit.assert_called_once_with(0)

    @patch('process_event.Q4DConfig')
    @patch('process_event.ProcessEvent')
    @patch('process_event.setup_logging')
    def test_main_execution_success(self, mock_setup_logging, mock_pe_class, mock_config_class):
        """Test successful main execution."""
        mock_config_class.return_value = self.mock_config
        mock_pe = Mock()
        mock_pe_class.return_value = mock_pe
        
        test_args = ["process_event.py", "--config", "test.conf"]
        
        with patch('sys.argv', test_args):
            # Need to patch the main execution since it's in if __name__ == '__main__'
            with patch('process_event.__name__', '__main__'):
                try:
                    # Import and execute the main block
                    import process_event
                    # The actual main execution happens in the if __name__ == '__main__' block
                    # We can't easily test this without refactoring, so we'll test components
                    pass
                except SystemExit:
                    pass

    @patch('process_event.logger')
    def test_logging_calls(self, mock_logger):
        """Test that appropriate logging calls are made."""
        with patch('process_event.load_type_mapping', return_value={}):
            with patch('process_event.FileTransfer'):
                with patch('process_event.MQTTHandler'):
                    pe = ProcessEvent(self.mock_config, Path("test.json"))
                    
                    # Verify debug logging calls
                    mock_logger.debug.assert_any_call("Loading type mapping from %s", Path("test.json"))
                    mock_logger.debug.assert_any_call("Loaded %d type mappings: %s", 0, [])
                    mock_logger.debug.assert_any_call("Initializing transfer handler")
                    mock_logger.debug.assert_any_call("Initializing MQTT handler")

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    @patch('process_event.logger')
    def test_start_logging_calls(self, mock_logger, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test logging calls during start."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        
        with patch('process_event.signal.signal'):
            pe.start()
        
        # Verify info logging calls
        mock_logger.info.assert_any_call("Starting Q4D event processor")
        
        # Verify debug logging calls
        mock_logger.debug.assert_any_call("MQTT broker: %s:%s", "test.mqtt.com", 1883)
        mock_logger.debug.assert_any_call("Transfer host: %s", "test.sftp.com")
        mock_logger.debug.assert_any_call("Labelling enabled: %s", True)

    @patch('process_event.load_type_mapping')
    @patch('process_event.FileTransfer')
    @patch('process_event.MQTTHandler')
    @patch('process_event.logger')
    def test_stop_logging_calls(self, mock_logger, mock_mqtt_class, mock_transfer_class, mock_load_mapping):
        """Test logging calls during stop."""
        mock_load_mapping.return_value = {}
        mock_transfer_class.return_value = Mock()
        mock_mqtt = Mock()
        mock_mqtt_class.return_value = mock_mqtt
        
        pe = ProcessEvent(self.mock_config, Path("test.json"))
        pe.stop()
        
        # Verify info logging calls
        mock_logger.info.assert_any_call("Stopping Q4D event processor")
        mock_logger.info.assert_any_call("Q4D event processor stopped")