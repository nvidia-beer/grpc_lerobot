#!/bin/bash
set -e

echo "Compiling protobuf files..."

# Compile the proto file
python -m grpc_tools.protoc \
    --proto_path=/workspace/grpc \
    --python_out=/workspace/grpc \
    --grpc_python_out=/workspace/grpc \
    /workspace/grpc/robot_data.proto

echo "Protobuf compilation complete!"

# Execute the command passed to the container
exec "$@"

