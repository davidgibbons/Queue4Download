FROM python:3.11-slim

# Install lftp and mosquitto-clients
RUN apt-get update && \
    apt-get install -y lftp mosquitto-clients && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app
# (Optional) Install Python dependencies if you have requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python client code
COPY app/ /app/

# Set the default command (update with your main script)
CMD ["python", "process_event.py"]