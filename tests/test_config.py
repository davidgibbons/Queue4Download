"""
Tests for the config module.
"""
import os
import tempfile
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from config import Q4DConfig, Q4DConfigError


class TestQ4DConfig:
    """Test cases for Q4DConfig class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Clear any existing environment variables
        env_vars = [f'Q4D_{key}' for key in ['BUS_HOST', 'BUS_PORT', 'USER', 'PW', 
                                             'LABELLING', 'CREDS', 'HOST', 'THREADS', 'SEGMENTS', 'PATH']]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    def teardown_method(self):
        """Clean up after each test method."""
        # Clear any environment variables set during tests
        env_vars = [f'Q4D_{key}' for key in ['BUS_HOST', 'BUS_PORT', 'USER', 'PW', 
                                             'LABELLING', 'CREDS', 'HOST', 'THREADS', 'SEGMENTS', 'PATH']]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

    @patch('config.Path')
    def test_init_with_valid_config_file(self, mock_path):
        """Test Q4DConfig initialization with valid config file."""
        # Create a mock config file that exists
        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = True
        
        # Mock Path() constructor calls
        def path_side_effect(arg):
            if str(arg).endswith('config.py'):
                # This is Path(__file__)
                mock_file_path = MagicMock()
                mock_file_path.parent.__truediv__.return_value = mock_config_file
                return mock_file_path
            else:
                # This is Path(some_path) for directory validation
                mock_q4d_path = MagicMock()
                mock_q4d_path.expanduser.return_value = mock_q4d_path
                mock_q4d_path.exists.return_value = True
                return mock_q4d_path
        
        mock_path.side_effect = path_side_effect
        
        # Mock Path.home() for the default PATH
        mock_path.home.return_value = Path('/home/user')
        
        # Mock the config file content
        with patch('config.configparser.ConfigParser') as mock_parser:
            mock_config_parser = MagicMock()
            mock_parser.return_value = mock_config_parser
            mock_config_parser.read.return_value = None
            mock_config_parser.has_section.return_value = True
            mock_config_parser.has_option.return_value = True
            mock_config_parser.get.side_effect = lambda section, key: {
                'BUS_HOST': 'test.mqtt.com',
                'BUS_PORT': '1883',
                'USER': 'testuser',
                'PW': 'testpass',
                'LABELLING': 'true',
                'CREDS': 'testcreds',
                'HOST': 'test.sftp.com',
                'THREADS': '4',
                'SEGMENTS': '8',
                'PATH': '/tmp/q4d'
            }[key]
            
            # Mock the subscriptable behavior for _config['DEFAULT']
            mock_default_section = MagicMock()
            mock_default_section.keys.return_value = ['BUS_HOST', 'BUS_PORT', 'USER', 'PW', 'LABELLING', 'CREDS', 'HOST', 'THREADS', 'SEGMENTS', 'PATH']
            mock_config_parser.__getitem__.return_value = mock_default_section
            
            config = Q4DConfig()
            
            # Verify config file was read
            mock_config_parser.read.assert_called_once()
            
            # Verify properties work
            assert config.bus_host == 'test.mqtt.com'
            assert config.bus_port == 1883
            assert config.user == 'testuser'
            assert config.pw == 'testpass'
            assert config.labelling is True
            assert config.creds == 'testcreds'
            assert config.host == 'test.sftp.com'
            assert config.threads == 4
            assert config.segments == 8
            assert config.q4d_path == '/tmp/q4d'

    @patch('config.Path')
    def test_init_with_missing_config_file(self, mock_path):
        """Test Q4DConfig initialization with missing config file."""
        # Create a mock config file that doesn't exist
        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = False
        
        # Mock Path() constructor calls
        def path_side_effect(arg):
            if str(arg).endswith('config.py'):
                # This is Path(__file__)
                mock_file_path = MagicMock()
                mock_file_path.parent.__truediv__.return_value = mock_config_file
                return mock_file_path
            else:
                # This is Path(some_path) for directory validation
                mock_q4d_path = MagicMock()
                mock_q4d_path.expanduser.return_value = mock_q4d_path
                mock_q4d_path.exists.return_value = True
                return mock_q4d_path
        
        mock_path.side_effect = path_side_effect
        
        # Mock Path.home() for the default PATH
        mock_path.home.return_value = Path('/home/user')
        
        # Set required environment variables
        os.environ['Q4D_BUS_HOST'] = 'env.mqtt.com'
        os.environ['Q4D_BUS_PORT'] = '1884'
        os.environ['Q4D_USER'] = 'envuser'
        os.environ['Q4D_PW'] = 'envpass'
        os.environ['Q4D_LABELLING'] = 'false'
        os.environ['Q4D_CREDS'] = 'envcreds'
        os.environ['Q4D_HOST'] = 'env.sftp.com'
        os.environ['Q4D_THREADS'] = '2'
        os.environ['Q4D_SEGMENTS'] = '4'
        os.environ['Q4D_PATH'] = '/tmp/env_q4d'
        
        with patch('config.configparser.ConfigParser') as mock_parser:
            mock_config_parser = MagicMock()
            mock_parser.return_value = mock_config_parser
            mock_config_parser.has_section.return_value = False
            mock_config_parser.has_option.return_value = False
            
            config = Q4DConfig()
            
            # Should use environment variables
            assert config.bus_host == 'env.mqtt.com'
            assert config.bus_port == 1884
            assert config.user == 'envuser'
            assert config.pw == 'envpass'
            assert config.labelling is False
            assert config.creds == 'envcreds'
            assert config.host == 'env.sftp.com'
            assert config.threads == 2
            assert config.segments == 4
            assert config.q4d_path == '/tmp/env_q4d'

    @patch('config.Path')
    def test_environment_variable_override(self, mock_path):
        """Test that environment variables override config file values."""
        # Create a mock config file that exists
        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = True
        
        # Mock Path() constructor calls
        def path_side_effect(arg):
            if str(arg).endswith('config.py'):
                # This is Path(__file__)
                mock_file_path = MagicMock()
                mock_file_path.parent.__truediv__.return_value = mock_config_file
                return mock_file_path
            else:
                # This is Path(some_path) for directory validation
                mock_q4d_path = MagicMock()
                mock_q4d_path.expanduser.return_value = mock_q4d_path
                mock_q4d_path.exists.return_value = True
                return mock_q4d_path
        
        mock_path.side_effect = path_side_effect
        
        # Mock Path.home() for the default PATH
        mock_path.home.return_value = Path('/home/user')
        
        # Set some environment variables
        os.environ['Q4D_BUS_HOST'] = 'override.mqtt.com'
        os.environ['Q4D_BUS_PORT'] = '9999'
        
        with patch('config.configparser.ConfigParser') as mock_parser:
            mock_config_parser = MagicMock()
            mock_parser.return_value = mock_config_parser
            mock_config_parser.read.return_value = None
            mock_config_parser.has_section.return_value = True
            mock_config_parser.has_option.side_effect = lambda section, key: key not in ['BUS_HOST', 'BUS_PORT']
            mock_config_parser.get.side_effect = lambda section, key: {
                'USER': 'configuser',
                'PW': 'configpass',
                'LABELLING': 'false',
                'CREDS': 'configcreds',
                'HOST': 'config.sftp.com',
                'THREADS': '3',
                'SEGMENTS': '6',
                'PATH': '/tmp/config_q4d'
            }[key]
            
            # Mock the subscriptable behavior for _config['DEFAULT']
            mock_default_section = MagicMock()
            mock_default_section.keys.return_value = ['USER', 'PW', 'LABELLING', 'CREDS', 'HOST', 'THREADS', 'SEGMENTS', 'PATH']
            mock_config_parser.__getitem__.return_value = mock_default_section
            
            config = Q4DConfig()
            
            # Environment variables should override config file
            assert config.bus_host == 'override.mqtt.com'
            assert config.bus_port == 9999
            
            # Config file values should be used where no env var exists
            assert config.user == 'configuser'
            assert config.pw == 'configpass'

    @patch('config.Path')
    def test_missing_required_value(self, mock_path):
        """Test that missing required values raise Q4DConfigError."""
        # Create a mock config file that doesn't exist
        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = False
        
        # Mock Path() constructor calls
        def path_side_effect(arg):
            if str(arg).endswith('config.py'):
                # This is Path(__file__)
                mock_file_path = MagicMock()
                mock_file_path.parent.__truediv__.return_value = mock_config_file
                return mock_file_path
            else:
                # This is Path(some_path) for directory validation
                mock_q4d_path = MagicMock()
                mock_q4d_path.expanduser.return_value = mock_q4d_path
                mock_q4d_path.exists.return_value = True
                return mock_q4d_path
        
        mock_path.side_effect = path_side_effect
        
        # Mock Path.home() for the default PATH
        mock_path.home.return_value = Path('/home/user')
        
        with patch('config.configparser.ConfigParser') as mock_parser:
            mock_config_parser = MagicMock()
            mock_parser.return_value = mock_config_parser
            mock_config_parser.has_section.return_value = False
            mock_config_parser.has_option.return_value = False
            
            # The first missing value checked is BUS_PORT, not BUS_HOST
            with pytest.raises(Q4DConfigError, match="Missing required configuration value: BUS_PORT"):
                Q4DConfig()

    def test_invalid_port_value(self):
        """Test that invalid port values raise Q4DConfigError."""
        # Set invalid port
        os.environ['Q4D_BUS_PORT'] = 'invalid'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        os.environ['Q4D_THREADS'] = '4'
        os.environ['Q4D_SEGMENTS'] = '8'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError, match="BUS_PORT must be an integer"):
                    Q4DConfig()

    def test_port_out_of_range(self):
        """Test that port values out of range raise Q4DConfigError."""
        # Set port out of range
        os.environ['Q4D_BUS_PORT'] = '70000'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        os.environ['Q4D_THREADS'] = '4'
        os.environ['Q4D_SEGMENTS'] = '8'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError, match="BUS_PORT must be between 1 and 65535"):
                    Q4DConfig()

    def test_invalid_threads_value(self):
        """Test that invalid threads values raise Q4DConfigError."""
        # Set invalid threads
        os.environ['Q4D_THREADS'] = 'invalid'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_BUS_PORT'] = '1883'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        os.environ['Q4D_SEGMENTS'] = '8'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError, match="THREADS must be an integer"):
                    Q4DConfig()

    def test_negative_threads_value(self):
        """Test that negative threads values raise Q4DConfigError."""
        # Set negative threads
        os.environ['Q4D_THREADS'] = '-1'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_BUS_PORT'] = '1883'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        os.environ['Q4D_SEGMENTS'] = '8'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError, match="THREADS must be a positive integer"):
                    Q4DConfig()

    def test_invalid_segments_value(self):
        """Test that invalid segments values raise Q4DConfigError."""
        # Set invalid segments
        os.environ['Q4D_SEGMENTS'] = 'invalid'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_BUS_PORT'] = '1883'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        os.environ['Q4D_THREADS'] = '4'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError, match="SEGMENTS must be an integer"):
                    Q4DConfig()

    @patch('config.Path')
    def test_labelling_boolean_values(self, mock_path):
        """Test that labelling property correctly parses boolean values."""
        # Create a mock config file that exists
        mock_config_file = MagicMock()
        mock_config_file.exists.return_value = True
        
        # Mock Path() constructor calls
        def path_side_effect(arg):
            if str(arg).endswith('config.py'):
                # This is Path(__file__)
                mock_file_path = MagicMock()
                mock_file_path.parent.__truediv__.return_value = mock_config_file
                return mock_file_path
            else:
                # This is Path(some_path) for directory validation
                mock_q4d_path = MagicMock()
                mock_q4d_path.expanduser.return_value = mock_q4d_path
                mock_q4d_path.exists.return_value = True
                return mock_q4d_path
        
        mock_path.side_effect = path_side_effect
        
        # Mock Path.home() for the default PATH
        mock_path.home.return_value = Path('/home/user')
        
        test_cases = [
            ('1', True),
            ('true', True),
            ('TRUE', True),
            ('yes', True),
            ('YES', True),
            ('on', True),
            ('ON', True),
            ('0', False),
            ('false', False),
            ('FALSE', False),
            ('no', False),
            ('NO', False),
            ('off', False),
            ('OFF', False),
            ('random', False),
        ]
        
        for value, expected in test_cases:
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.read.return_value = None
                mock_config_parser.has_section.return_value = True
                mock_config_parser.has_option.return_value = True
                mock_config_parser.get.side_effect = lambda section, key: {
                    'BUS_HOST': 'test.mqtt.com',
                    'BUS_PORT': '1883',
                    'USER': 'testuser',
                    'PW': 'testpass',
                    'LABELLING': value,
                    'CREDS': 'testcreds',
                    'HOST': 'test.sftp.com',
                    'THREADS': '4',
                    'SEGMENTS': '8',
                    'PATH': '/tmp/q4d'
                }[key]
                
                # Mock the subscriptable behavior for _config['DEFAULT']
                mock_default_section = MagicMock()
                mock_default_section.keys.return_value = ['BUS_HOST', 'BUS_PORT', 'USER', 'PW', 'LABELLING', 'CREDS', 'HOST', 'THREADS', 'SEGMENTS', 'PATH']
                mock_config_parser.__getitem__.return_value = mock_default_section
                
                config = Q4DConfig()
                assert config.labelling is expected, f"Value '{value}' should be {expected}"

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are collected and reported."""
        # Set multiple invalid values
        os.environ['Q4D_BUS_PORT'] = 'invalid'
        os.environ['Q4D_THREADS'] = '-1'
        os.environ['Q4D_SEGMENTS'] = 'invalid'
        os.environ['Q4D_BUS_HOST'] = 'test.com'
        os.environ['Q4D_USER'] = 'user'
        os.environ['Q4D_PW'] = 'pass'
        os.environ['Q4D_LABELLING'] = 'true'
        os.environ['Q4D_CREDS'] = 'creds'
        os.environ['Q4D_HOST'] = 'host'
        
        with patch('config.Path') as mock_path:
            # Create a mock config file that doesn't exist
            mock_config_file = MagicMock()
            mock_config_file.exists.return_value = False
            
            # Mock Path() constructor calls
            def path_side_effect(arg):
                if str(arg).endswith('config.py'):
                    # This is Path(__file__)
                    mock_file_path = MagicMock()
                    mock_file_path.parent.__truediv__.return_value = mock_config_file
                    return mock_file_path
                else:
                    # This is Path(some_path) for directory validation
                    mock_q4d_path = MagicMock()
                    mock_q4d_path.expanduser.return_value = mock_q4d_path
                    mock_q4d_path.exists.return_value = True
                    return mock_q4d_path
            
            mock_path.side_effect = path_side_effect
            
            # Mock Path.home() for the default PATH
            mock_path.home.return_value = Path('/home/user')
            
            with patch('config.configparser.ConfigParser') as mock_parser:
                mock_config_parser = MagicMock()
                mock_parser.return_value = mock_config_parser
                mock_config_parser.has_section.return_value = False
                mock_config_parser.has_option.return_value = False
                
                with pytest.raises(Q4DConfigError) as exc_info:
                    Q4DConfig()
                
                error_message = str(exc_info.value)
                assert "BUS_PORT must be an integer" in error_message
                assert "THREADS must be a positive integer" in error_message
                assert "SEGMENTS must be an integer" in error_message 