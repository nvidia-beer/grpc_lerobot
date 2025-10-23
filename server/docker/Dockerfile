FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY server/docker/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set working directory
WORKDIR /workspace

# Copy entrypoint script
COPY server/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Files will be mounted as volumes at runtime
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "server/ui_server.py"]

