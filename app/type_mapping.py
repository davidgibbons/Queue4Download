"""
Type mapping module for Q4D client.
Handles loading and managing type code to directory mappings.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("TypeMapping")

def load_type_mapping(type_mapping_path: Path):
    """Load type mapping from JSON file."""
    logger.debug("Loading type mapping from: %s", type_mapping_path)
    logger.debug("Type mapping file exists: %s", type_mapping_path.exists())

    if not type_mapping_path.exists():
        logger.error("Type mapping file not found: %s", type_mapping_path)
        raise FileNotFoundError(f"Type mapping file not found: {type_mapping_path}")

    try:
        logger.debug("Reading type mapping file: %s", type_mapping_path)
        with open(type_mapping_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
            logger.info("Loaded type mapping from %s", type_mapping_path)
            logger.debug("Type mapping contents: %s", mapping)
            logger.debug("Number of type codes: %d", len(mapping))

            # Validate mapping contents
            for code, directory in mapping.items():
                logger.debug("Type mapping entry: %s -> %s", code, directory)
                if not isinstance(code, str) or not isinstance(directory, str):
                    logger.warning("Invalid type mapping entry: %s -> %s "
                                   "(should be string -> string)", code, directory)

            return mapping
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in type mapping file %s: %s", type_mapping_path, e)
        logger.debug("JSON decode error details: %s", e)
        raise ValueError(f"Invalid JSON in type mapping file {type_mapping_path}: {e}") from e
    except IOError as e:
        logger.error("Failed to read type mapping file %s: %s", type_mapping_path, e)
        logger.debug("IO error details: %s", e)
        raise IOError(f"Failed to read type mapping file {type_mapping_path}: {e}") from e
