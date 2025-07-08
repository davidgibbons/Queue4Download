"""
Q4D Event Processor - Main entry point.
Coordinates MQTT event handling and file transfers.

Requirements:
    pip install paho-mqtt
"""
import sys
import logging
import argparse
import signal
from pathlib import Path

from config import Q4DConfig
from transfer import FileTransfer
from mqtt_handler import MQTTHandler
from type_mapping import load_type_mapping

def setup_logging(debug=False):
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger("ProcessEvent")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Q4D Event Processor')
    parser.add_argument(
        '--config',
        type=str,
        default='q4d.conf',
        help='Path to Q4D configuration file (default: q4d.conf)'
    )
    parser.add_argument(
        '--type-mapping',
        type=str,
        default='type_mapping.json',
        help='Path to type mapping JSON file (default: type_mapping.json)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    return parser.parse_args()

class ProcessEvent:
    """Main event processor that coordinates MQTT and transfer handling."""

    def __init__(self, event_config: Q4DConfig, mapping_path: Path):
        """Initialize the process event handler."""
        self.config = event_config
        logger.debug("Loading type mapping from %s", mapping_path)
        type_to_dir = load_type_mapping(mapping_path)
        logger.debug("Loaded %d type mappings: %s",
                     len(type_to_dir), list(type_to_dir.keys()))

        logger.debug("Initializing transfer handler")
        self.transfer_handler = FileTransfer(event_config, type_to_dir)

        logger.debug("Initializing MQTT handler")
        self.mqtt_handler = MQTTHandler(event_config, self.transfer_handler)

    def start(self):
        """Start the event processor."""
        logger.info("Starting Q4D event processor")
        logger.debug("MQTT broker: %s:%s", self.config.bus_host, self.config.bus_port)
        logger.debug("Transfer host: %s", self.config.host)
        logger.debug("Labelling enabled: %s", self.config.labelling)

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, _frame):
            logger.info("Received signal %d, shutting down gracefully...", signum)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            self.mqtt_handler.start()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("MQTT handler failed: %s", e)
            logger.debug("MQTT handler exception details:", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """Stop the event processor gracefully."""
        logger.info("Stopping Q4D event processor")
        if hasattr(self, 'mqtt_handler'):
            self.mqtt_handler.stop()
        logger.info("Q4D event processor stopped")

if __name__ == '__main__':
    args = parse_arguments()
    setup_logging(debug=args.debug)

    logger.debug("Starting with args: config=%s, type_mapping=%s, debug=%s",
                 args.config, args.type_mapping, args.debug)

    # Resolve paths relative to script directory if not absolute
    script_dir = Path(__file__).parent
    config_path = (Path(args.config) if Path(args.config).is_absolute()
                   else script_dir / args.config)
    type_mapping_path = (Path(args.type_mapping) if Path(args.type_mapping).is_absolute()
                         else script_dir / args.type_mapping)

    logger.debug("Resolved config path: %s", config_path)
    logger.debug("Resolved type mapping path: %s", type_mapping_path)

    try:
        logger.debug("Loading configuration")
        config = Q4DConfig(str(config_path))
        logger.debug("Configuration loaded successfully")

        pe = ProcessEvent(config, type_mapping_path)
        pe.start()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to start Q4D event processor: %s", e)
        logger.debug("Exception details:", exc_info=True)
        sys.exit(1)
