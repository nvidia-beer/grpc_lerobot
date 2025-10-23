#!/bin/bash
set -e

# Configuration
GRPC_PORT="${1:-50051}"
WEB_PORT="${2:-8080}"
CONTAINER_NAME="grpc-lerobot-server"

# Go to project root
cd "$(dirname "$0")"

echo "Starting gRPC Server - gRPC: $GRPC_PORT, Web UI: http://localhost:$WEB_PORT"

# Build image
docker build -t "$CONTAINER_NAME" -f server/docker/Dockerfile .

# Stop and remove existing container
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Run server
docker run \
    --name "$CONTAINER_NAME" \
    --network=host \
    -e PYTHONPATH="/workspace/grpc" \
    -v "$(pwd):/workspace" \
    -w /workspace \
    "$CONTAINER_NAME" \
    python server/ui_server.py --grpc-port "$GRPC_PORT" --web-port "$WEB_PORT" --host 0.0.0.0
