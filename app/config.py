"""
Configuration module for Q4D client.
Handles loading and validation of Q4D configuration from files and environment variables.
"""
import os
import sys
import configparser
import logging
from pathlib import Path

logger = logging.getLogger("Config")


class Q4DConfigError(Exception):
    """Custom exception for Q4D configuration errors."""


class Q4DConfig:
    """Configuration manager for Q4D client settings."""

    # Only provide a default for PATH, as it's needed to bootstrap config file location
    DEFAULTS = {
        'PATH': str(Path.home() / '.Q4D'),
    }

    def __init__(self, config_file='q4d.conf'):
        """Initialize Q4DConfig with configuration file."""
        logger.debug("Initializing Q4DConfig with config file: %s", config_file)
        self.config_file = Path(__file__).parent / config_file
        logger.debug("Resolved config file path: %s", self.config_file)
        logger.debug("Config file exists: %s", self.config_file.exists())

        self._config = configparser.ConfigParser()
        if self.config_file.exists():
            logger.debug("Reading config file: %s", self.config_file)
            self._config.read(self.config_file)
            logger.debug("Config sections: %s", self._config.sections())
            if self._config.has_section('DEFAULT'):
                logger.debug("DEFAULT section keys: %s",
                           list(self._config['DEFAULT'].keys()))
        else:
            logger.warning("Config file not found: %s", self.config_file)

        logger.debug("Starting config validation")
        self._validate_config()
        logger.debug("Config validation completed successfully")

    def _get(self, key):
        """Get configuration value with environment variable override."""
        env_key = f'Q4D_{key}'
        logger.debug("Getting config value for key: %s (env var: %s)", key, env_key)

        if env_key in os.environ:
            value = os.environ[env_key]
            logger.debug("Found %s in environment: %s", key, value)
            return value
        if self._config.has_option('DEFAULT', key):
            value = self._config.get('DEFAULT', key)
            logger.debug("Found %s in config file: %s", key, value)
            return value
        # Only provide a default for PATH
        if key in self.DEFAULTS:
            value = self.DEFAULTS[key]
            logger.debug("Using default for %s: %s", key, value)
            return value

        logger.error("Missing required configuration value: %s", key)
        raise Q4DConfigError(f"Missing required configuration value: {key}")

    def _validate_config(self):
        """Validate configuration values and raise clear errors if invalid."""
        errors = []

        # Validate BUS_PORT is an integer
        try:
            port = int(self._get('BUS_PORT'))
            logger.debug("Validating BUS_PORT: %s", port)
            if not 1 <= port <= 65535:
                errors.append(f"BUS_PORT must be between 1 and 65535, got {port}")
        except ValueError as e:
            logger.debug("BUS_PORT validation failed: %s", e)
            errors.append(f"BUS_PORT must be an integer, got '{self._get('BUS_PORT')}'")

        # Validate THREADS is a positive integer
        try:
            threads = int(self._get('THREADS'))
            logger.debug("Validating THREADS: %s", threads)
            if threads < 1:
                errors.append(f"THREADS must be a positive integer, got {threads}")
        except ValueError as e:
            logger.debug("THREADS validation failed: %s", e)
            errors.append(f"THREADS must be an integer, got '{self._get('THREADS')}'")

        # Validate SEGMENTS is a positive integer
        try:
            segments = int(self._get('SEGMENTS'))
            logger.debug("Validating SEGMENTS: %s", segments)
            if segments < 1:
                errors.append(f"SEGMENTS must be a positive integer, got {segments}")
        except ValueError as e:
            logger.debug("SEGMENTS validation failed: %s", e)
            errors.append(f"SEGMENTS must be an integer, got '{self._get('SEGMENTS')}'")

        # Validate Q4D_PATH exists or can be created
        q4d_path = Path(self._get('PATH')).expanduser()
        logger.debug("Validating Q4D_PATH: %s", q4d_path)
        if not q4d_path.exists():
            try:
                logger.debug("Creating Q4D_PATH directory: %s", q4d_path)
                q4d_path.mkdir(parents=True, exist_ok=True)
                logger.debug("Successfully created Q4D_PATH: %s", q4d_path)
            except OSError as e:
                logger.debug("Failed to create Q4D_PATH: %s", e)
                errors.append(f"Q4D_PATH '{q4d_path}' cannot be created: {e}")
        else:
            logger.debug("Q4D_PATH already exists: %s", q4d_path)

        if errors:
            logger.error("Configuration validation failed with %d errors", len(errors))
            for error in errors:
                logger.debug("Validation error: %s", error)
            raise Q4DConfigError("Configuration validation failed:\n" +
                               "\n".join(f"  - {error}" for error in errors))

    @property
    def q4d_path(self):
        """Get Q4D path configuration."""
        return self._get('PATH')

    @property
    def bus_host(self):
        """Get MQTT bus host configuration."""
        return self._get('BUS_HOST')

    @property
    def bus_port(self):
        """Get MQTT bus port configuration."""
        return int(self._get('BUS_PORT'))

    @property
    def user(self):
        """Get MQTT user configuration."""
        return self._get('USER')

    @property
    def pw(self):
        """Get MQTT password configuration."""
        return self._get('PW')

    @property
    def labelling(self):
        """Get labelling configuration as boolean."""
        val = self._get('LABELLING')
        result = str(val).lower() in ('1', 'true', 'yes', 'on')
        logger.debug("Labelling config: '%s' -> %s", val, result)
        return result

    @property
    def creds(self):
        """Get SFTP credentials configuration."""
        return self._get('CREDS')

    @property
    def host(self):
        """Get SFTP host configuration."""
        return self._get('HOST')

    @property
    def threads(self):
        """Get transfer threads configuration."""
        return int(self._get('THREADS'))

    @property
    def segments(self):
        """Get transfer segments configuration."""
        return int(self._get('SEGMENTS'))


def _example():
    """Example usage of Q4DConfig."""
    try:
        config = Q4DConfig()
        print('Q4D_PATH:', config.q4d_path)
        print('BUS_HOST:', config.bus_host)
        print('BUS_PORT:', config.bus_port)
        print('USER:', config.user)
        print('PW:', '***' if config.pw else 'not set')
        print('LABELLING:', config.labelling)
        print('CREDS:', '***' if config.creds else 'not set')
        print('HOST:', config.host)
        print('THREADS:', config.threads)
        print('SEGMENTS:', config.segments)
    except Q4DConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    _example()
