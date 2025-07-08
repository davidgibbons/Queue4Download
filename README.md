# Queue4Download

![Tests](https://github.com/davidgibbons/Queue4Download/workflows/Tests/badge.svg)
![PR Tests](https://github.com/davidgibbons/Queue4Download/workflows/PR%20Tests/badge.svg)
![Python Support](https://img.shields.io/badge/python-3.8%2B-blue)

Modern Python implementation of Q4D - automated push notification system for completed torrent payloads with integration into home media libraries and remote torrent client labelling.

## Why Q4D?

Seedboxes have limited storage, if you want to retain your payloads in a media library application like Plex, Jellyfin, Kodi or Emby you need to copy from your seedbox to home. This is currently not well integrated into torrent clients, and requires automation that 'syncs' your media libraries, packages like rsync, syncthing or resilio - all of which poll your seedbox (say every hour or half hour), and copy anything new home - relying on directory structure and linking to organize your media.

Queue4Download addresses all of these issues - the scripts integrate directly with the torrent client, and can use labelling to capture progress. By using a lightweight message bus like Mosquitto, the process becomes a push not a pull, no more polling. The torrent finishes, the event is queued and captured by your home server, which spawns an LFTP job from home to transfer (very fast) from where the torrent lives to where you specify in your media library. Destinations are mapped by you, based on such criteria as tracker, title, path or label. Queue4Download is written to handle torrents, unlike generic utilities. This means that usually it is minutes, not hours that your media appears in your media server. All automated.

## Architecture

The system consists of server-side scripts (seedbox) and a Python client application (home server):

### Server (Seedbox)

Queue4Download.sh - Torrent client hook Script. Throws an event upon completion of the torrent, event contains the payload name/path (where LFTP will find the payload), the payload hash (for label updates once the transfer is complete), and a simple category code (tells home where to put the payload, ie /Media/Movies)

LabelD.sh - Daemon script to listen for Label events and change the torrent label

Types.config - Flat file declarations for type code assignment (space separated lines: FIELD CONDITIONAL VALUE TYPE SCOPE)

Q4Dconfig.sh - MQTT co-ords, torrent client, and labelling definitions (needed on both client and server)

### Client (Home Server)

The client is now a modern Python application (`process_event.py`) that:

- Connects to your MQTT broker and listens for download completion events
- Automatically triggers LFTP transfers based on configured type mappings
- Handles concurrent downloads with configurable thread limits
- Provides comprehensive logging and error handling
- Supports graceful shutdown and signal handling

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- LFTP for file transfers
- Access to an MQTT broker (Mosquitto recommended)
- Seedbox/server with bash/ssh access for server scripts

### Client Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the application:**
   
   Edit `app/q4d.conf` with your settings:
   ```ini
   [DEFAULT]
   BUS_HOST = your.mqtt.broker.com
   BUS_PORT = 1883
   USER = your_mqtt_username
   PW = your_mqtt_password
   LABELLING = true
   CREDS = your_sftp_credentials
   HOST = your.seedbox.com
   THREADS = 4
   SEGMENTS = 8
   PATH = /path/to/your/downloads
   ```

   Or use environment variables (prefix with `Q4D_`):
   ```bash
   export Q4D_BUS_HOST=your.mqtt.broker.com
   export Q4D_BUS_PORT=1883
   # ... etc
   ```

3. **Configure type mappings:**
   
   Edit `app/type_mapping.json` to map category codes to local directories:
   ```json
   {
     "MOV": "/media/movies",
     "TV": "/media/tv",
     "MUSIC": "/media/music"
   }
   ```

4. **Run the client:**
   ```bash
   # Run in foreground with debug logging
   python app/process_event.py --debug
   
   # Run as daemon (production)
   python app/process_event.py --daemon
   
   # Custom configuration file
   python app/process_event.py --config /path/to/custom.conf
   ```

### Docker Setup

For containerized deployment, Q4D provides Docker support with pre-built images.

#### Using Docker (Standalone)

```bash
# Pull the latest image
docker pull ghcr.io/davidgibbons/queue4download:latest

# Run with environment variables
docker run -d \
  --name q4d-client \
  --restart unless-stopped \
  -e Q4D_BUS_HOST=mqtt.your-broker.com \
  -e Q4D_BUS_PORT=1883 \
  -e Q4D_USER=your_mqtt_username \
  -e Q4D_PW=your_mqtt_password \
  -e Q4D_HOST=your.seedbox.com \
  -e Q4D_THREADS=4 \
  -e Q4D_SEGMENTS=8 \
  -e Q4D_PATH=/downloads \
  -v /local/downloads:/downloads \
  -v /local/credentials:/app/credentials:ro \
  -v /local/type_mapping.json:/app/type_mapping.json:ro \
  ghcr.io/davidgibbons/queue4download:latest
```

#### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  q4d-client:
    image: ghcr.io/davidgibbons/queue4download:latest
    container_name: q4d-client
    restart: unless-stopped
    
    # Environment variables for Q4D configuration
    environment:
      - Q4D_BUS_HOST=mqtt.your-broker.com
      - Q4D_BUS_PORT=1883
      - Q4D_USER=your_mqtt_username
      - Q4D_PW=your_mqtt_password
      - Q4D_LABELLING=true
      - Q4D_CREDS=/app/credentials
      - Q4D_HOST=your.seedbox.com
      - Q4D_THREADS=4
      - Q4D_SEGMENTS=8
      - Q4D_PATH=/downloads
      
    # Volume mounts
    volumes:
      # Mount local downloads directory
      - ./downloads:/downloads
      # Mount SFTP credentials
      - ./credentials:/app/credentials:ro
      # Mount type mapping (optional override)
      - ./type_mapping.json:/app/type_mapping.json:ro
      
    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        
    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import paho.mqtt.client as mqtt; print('OK')"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: Local MQTT broker for testing
  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: q4d-mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
    profiles:
      - testing
```

Then run:

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f q4d-client

# Stop the service
docker-compose down
```

#### Environment Variables for Docker

All configuration options can be set via environment variables by prefixing with `Q4D_`:

| Environment Variable | Description | Example |
|---------------------|-------------|---------|
| `Q4D_BUS_HOST` | MQTT broker hostname | `mqtt.broker.com` |
| `Q4D_BUS_PORT` | MQTT broker port | `1883` |
| `Q4D_USER` | MQTT username | `your_username` |
| `Q4D_PW` | MQTT password | `your_password` |
| `Q4D_LABELLING` | Enable torrent labelling | `true` |
| `Q4D_CREDS` | SFTP credentials file path | `/app/credentials` |
| `Q4D_HOST` | Seedbox hostname | `seedbox.com` |
| `Q4D_THREADS` | Concurrent transfer threads | `4` |
| `Q4D_SEGMENTS` | LFTP segments per transfer | `8` |
| `Q4D_PATH` | Local download directory | `/downloads` |

#### Building Your Own Image

If you want to build the Docker image locally:

```bash
# Build the image
docker build -t q4d-client .

# Run your local build
docker run -d --name q4d-client q4d-client
```

### Server Setup

Server scripts remain unchanged from the original implementation. See the legacy documentation for bash script configuration on your seedbox.

## Configuration Options

### Command Line Arguments

- `--config`: Path to configuration file (default: `app/q4d.conf`)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `--daemon`: Run as background daemon
- `--debug`: Enable debug logging (equivalent to `--log-level DEBUG`)

### Configuration File Options

| Setting | Description | Default |
|---------|-------------|---------|
| `BUS_HOST` | MQTT broker hostname | Required |
| `BUS_PORT` | MQTT broker port | 1883 |
| `USER` | MQTT username | Required |
| `PW` | MQTT password | Required |
| `LABELLING` | Enable torrent labelling | true |
| `CREDS` | SFTP credentials file | Required |
| `HOST` | Seedbox hostname | Required |
| `THREADS` | Concurrent transfer threads | 4 |
| `SEGMENTS` | LFTP segments per transfer | 8 |
| `PATH` | Local download directory | Required |

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_config.py -v
```

### Code Quality

The project uses GitHub Actions for continuous integration:

- **Full test matrix** - Tests across Python 3.8-3.12 on Ubuntu, Windows, and macOS
- **Pull request checks** - Fast feedback with linting and test coverage
- **Security scanning** - Dependency vulnerability checks with Safety and Bandit
- **Code quality** - Linting with flake8 and optional type checking with mypy

### Test Coverage

The test suite includes comprehensive coverage:

- **Config module** - Configuration loading, validation, and environment variable handling
- **MQTT handler** - MQTT client operations, connection handling, and message processing  
- **Process event** - Main application logic, argument parsing, and signal handling
- **Transfer** - File transfer operations and LFTP command execution
- **Type mapping** - JSON configuration loading and error handling

## Legacy Documentation

For historical reference and server-side bash script setup:

- [Q4D Updated](https://www.reddit.com/r/sbtech/comments/1ams0hn/q4d_updated/)
- [Original Queue4Download](https://www.reddit.com/r/Chmuranet/comments/f3lghf/queue4download_scripts_to_handle_torrent_complete/)
- [SBTech Discussion](https://www.reddit.com/r/sbtech/comments/nih988/queue4download_scripts_to_handle_torrent_complete/)

## License

This project maintains compatibility with the original Q4D implementation while modernizing the client-side components for better maintainability and reliability.
