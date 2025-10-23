FROM huggingface/lerobot-cpu

# Install gRPC and YAML dependencies
COPY client/docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set working directory
WORKDIR /workspace

# Copy entrypoint script
COPY --chmod=755 client/docker/entrypoint.sh /entrypoint.sh

# The actual files will be mounted as volumes
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "client/grpc_client.py"]

