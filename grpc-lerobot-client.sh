#!/bin/bash
set -e

# Configuration
SERVER="${GRPC_SERVER:-localhost:50051}"
CONTAINER_NAME="grpc-lerobot-client"
# DEBUG_JOINTS="--debug-joints gripper shoulder_pan"  # Uncomment for debug mode
DEBUG_JOINTS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server) SERVER="$2"; shift 2 ;;
        --debug-joints) 
            # Collect all joint names after --debug-joints
            shift
            DEBUG_JOINTS="--debug-joints"
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                DEBUG_JOINTS="$DEBUG_JOINTS $1"
                shift
            done
            ;;
        *) echo "Usage: $0 [--server <address:port>] [--debug-joints <joint_names...>]"; exit 1 ;;
    esac
done

# Go to project root
cd "$(dirname "$0")"

echo "Starting gRPC Client - Server: $SERVER"

# Build image
docker build -t "$CONTAINER_NAME" -f client/docker/Dockerfile .

# Stop and remove existing container
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Run client
docker run \
    --name "$CONTAINER_NAME" \
    --network=host \
    --privileged \
    --user root \
    -e PYTHONPATH="/workspace/grpc" \
    -v /dev/bus/usb:/dev/bus/usb \
    -v "$(pwd):/workspace" \
    -w /workspace \
    "$CONTAINER_NAME" \
    python client/grpc_client.py --config client/config.yaml --server "$SERVER" --rate 30 --calibration calibration $DEBUG_JOINTS
