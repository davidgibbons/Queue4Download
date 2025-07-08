"""
Tests for the type_mapping module.
"""
import json
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from type_mapping import load_type_mapping


class TestTypeMapping:
    """Test cases for type mapping functionality."""

    def test_load_valid_json_file(self):
        """Test loading a valid JSON file."""
        test_data = {"MOV": "/downloads/movies", "TV": "/downloads/tv"}
        mock_file_content = json.dumps(test_data)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = load_type_mapping(mock_path)
                
        assert result == test_data

    def test_load_empty_json_file(self):
        """Test loading an empty JSON file."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data='{}')):
            result = load_type_mapping(mock_path)
                
        assert result == {}

    def test_load_file_not_found(self):
        """Test handling of file not found."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="Type mapping file not found"):
            load_type_mapping(mock_path)

    def test_load_invalid_json(self):
        """Test handling of invalid JSON."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data='invalid json')):
            with pytest.raises(ValueError, match="Invalid JSON in type mapping file"):
                load_type_mapping(mock_path)

    def test_load_json_with_unicode(self):
        """Test loading JSON with Unicode characters."""
        test_data = {"ANIME": "/downloads/アニメ", "FILM": "/downloads/películas"}
        mock_file_content = json.dumps(test_data, ensure_ascii=False)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = load_type_mapping(mock_path)
                
        assert result == test_data

    def test_load_large_json_file(self):
        """Test loading a large JSON file."""
        # Create a large mapping
        test_data = {f"TYPE_{i}": f"/downloads/type_{i}" for i in range(1000)}
        mock_file_content = json.dumps(test_data)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = load_type_mapping(mock_path)
                
        assert result == test_data
        assert len(result) == 1000

    def test_load_json_with_special_characters(self):
        """Test loading JSON with special characters in keys/values."""
        test_data = {
            "TYPE@#$": "/downloads/special!@#",
            "TYPE WITH SPACES": "/downloads/with spaces",
            "TYPE-WITH-DASHES": "/downloads/with-dashes"
        }
        mock_file_content = json.dumps(test_data)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = load_type_mapping(mock_path)
                
        assert result == test_data

    def test_load_json_io_error(self):
        """Test handling of IO errors."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Failed to read type mapping file"):
                load_type_mapping(mock_path)

    def test_load_json_permission_error(self):
        """Test handling of permission errors."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(IOError, match="Failed to read type mapping file"):
                load_type_mapping(mock_path)

    def test_load_json_with_nested_structures(self):
        """Test loading JSON with nested structures (should still work)."""
        test_data = {
            "MOV": {
                "path": "/downloads/movies",
                "quality": "1080p"
            },
            "TV": {
                "path": "/downloads/tv",
                "quality": "720p"
            }
        }
        mock_file_content = json.dumps(test_data)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            result = load_type_mapping(mock_path)
                
        assert result == test_data

    def test_load_non_dict_json(self):
        """Test loading JSON that's not a dictionary."""
        test_data = ["item1", "item2", "item3"]
        mock_file_content = json.dumps(test_data)

        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True

        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            # Should raise AttributeError because list doesn't have .items() method
            with pytest.raises(AttributeError, match="'list' object has no attribute 'items'"):
                load_type_mapping(mock_path)

    @patch('type_mapping.logger')
    def test_logging_calls(self, mock_logger):
        """Test that appropriate logging calls are made."""
        test_data = {"MOV": "/downloads/movies"}
        mock_file_content = json.dumps(test_data)
        
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            load_type_mapping(mock_path)
                
        # Should log successful loading
        mock_logger.info.assert_called_with("Loaded type mapping from %s", mock_path)
        mock_logger.debug.assert_any_call("Loading type mapping from: %s", mock_path)
        mock_logger.debug.assert_any_call("Type mapping contents: %s", test_data) 