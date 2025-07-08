"""
Tests for the transfer module.
"""
import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from transfer import FileTransfer


class TestFileTransfer:
    """Test cases for FileTransfer class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_config = Mock()
        self.mock_config.creds = "testuser:testpass"
        self.mock_config.host = "test.sftp.com"
        self.mock_config.threads = 4
        self.mock_config.segments = 8
        self.mock_type_mapping = {"MOV": "/downloads/movies", "TV": "/downloads/tv", "ERR": "/downloads/errors"}

    def test_init_creates_transfer_object(self):
        """Test that FileTransfer initializes correctly."""
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        assert transfer.config == self.mock_config
        assert transfer.type_to_dir == self.mock_type_mapping

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    @patch('transfer.os.chmod')
    def test_transfer_file_success_mirror(self, mock_chmod, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test successful file transfer using mirror command."""
        # Setup mocks
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        # Verify directory check and change
        mock_isdir.assert_called_once_with("/downloads/movies")
        mock_chdir.assert_called_once_with("/downloads/movies")
        
        # Verify lftp command was called
        mock_run.assert_called_once()
        assert result is True

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    @patch('transfer.os.chmod')
    def test_transfer_file_success_pget_fallback(self, mock_chmod, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test successful file transfer using pget fallback when mirror fails."""
        # Setup mocks
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        # First call (mirror) fails, second call (pget) succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "lftp", "Mirror failed"),
            Mock(returncode=0, stdout="Success", stderr="")
        ]
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        # Verify both commands were attempted
        assert mock_run.call_count == 2
        assert result is True

    @patch('transfer.os.path.isdir')
    def test_transfer_file_unknown_type_with_err_fallback(self, mock_isdir):
        """Test transfer with unknown type code falls back to ERR."""
        mock_isdir.return_value = True
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        with patch('transfer.os.chdir'), \
             patch('transfer.shutil.which', return_value="/usr/bin/lftp"), \
             patch('transfer.subprocess.run') as mock_run, \
             patch('transfer.os.chmod'):
            
            mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
            
            result = transfer.transfer_file("/remote/unknown.file", "hash123", "UNKNOWN")
            
            # Should use ERR directory
            mock_isdir.assert_called_with("/downloads/errors")
            assert result is True

    @patch('transfer.os.path.isdir')
    def test_transfer_file_unknown_type_no_err_fallback(self, mock_isdir):
        """Test transfer with unknown type code and no ERR fallback fails."""
        mock_isdir.return_value = True
        type_mapping_no_err = {"MOV": "/downloads/movies", "TV": "/downloads/tv"}
        
        transfer = FileTransfer(self.mock_config, type_mapping_no_err)
        
        result = transfer.transfer_file("/remote/unknown.file", "hash123", "UNKNOWN")
        
        assert result is False

    @patch('transfer.os.path.isdir')
    def test_transfer_file_directory_not_exists(self, mock_isdir):
        """Test transfer failure when destination directory doesn't exist."""
        mock_isdir.return_value = False
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        assert result is False

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    def test_transfer_file_chdir_failure(self, mock_chdir, mock_isdir):
        """Test transfer failure when cannot change to destination directory."""
        mock_isdir.return_value = True
        mock_chdir.side_effect = OSError("Permission denied")
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        assert result is False

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    def test_transfer_file_lftp_not_installed(self, mock_which, mock_chdir, mock_isdir):
        """Test transfer failure when lftp is not installed."""
        mock_isdir.return_value = True
        mock_which.return_value = None
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        assert result is False

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    def test_transfer_file_both_commands_fail(self, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test transfer failure when both mirror and pget commands fail."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "lftp", "Mirror failed"),
            subprocess.CalledProcessError(1, "lftp", "Pget failed")
        ]
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        assert result is False
        assert mock_run.call_count == 2

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    @patch('transfer.os.chmod')
    def test_transfer_file_chmod_failure(self, mock_chmod, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test that chmod failure doesn't prevent successful transfer."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        mock_chmod.side_effect = OSError("Permission denied")
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        result = transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        # Should still succeed despite chmod failure
        assert result is True

    @patch('transfer.logger')
    def test_logging_calls(self, mock_logger):
        """Test that appropriate logging calls are made."""
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        
        # Verify debug logging during initialization
        mock_logger.debug.assert_any_call("FileTransfer initialized with %d type mappings", 3)
        mock_logger.debug.assert_any_call("Transfer config - host: %s, threads: %d, segments: %d",
                                          "test.sftp.com", 4, 8)

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    @patch('transfer.os.chmod')
    @patch('transfer.logger')
    def test_transfer_logging_success(self, mock_logger, mock_chmod, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test logging during successful transfer."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        # Verify success logging
        mock_logger.info.assert_any_call("Transfer of %s to %s completed successfully", 
                                         "/remote/movie.mkv", "/downloads/movies")

    @patch('transfer.os.path.isdir')
    @patch('transfer.os.chdir')
    @patch('transfer.shutil.which')
    @patch('transfer.subprocess.run')
    @patch('transfer.logger')
    def test_transfer_logging_failure(self, mock_logger, mock_run, mock_which, mock_chdir, mock_isdir):
        """Test logging during failed transfer."""
        mock_isdir.return_value = True
        mock_which.return_value = "/usr/bin/lftp"
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "lftp", "Mirror failed"),
            subprocess.CalledProcessError(1, "lftp", "Pget failed")
        ]
        
        transfer = FileTransfer(self.mock_config, self.mock_type_mapping)
        transfer.transfer_file("/remote/movie.mkv", "hash123", "MOV")
        
        # Verify failure logging
        mock_logger.error.assert_any_call("Transfer of %s to %s failed", 
                                          "/remote/movie.mkv", "/downloads/movies") 