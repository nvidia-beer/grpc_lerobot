# gRPC Server

Run the gRPC server with Web UI in Docker.

## Quick Start

```bash
# Default ports (gRPC: 50051, Web: 8070)
./grpc-server.sh

# Custom ports
./grpc-server.sh 50052 8080
```

Access Web UI at `http://localhost:8070`

## Files

- `grpc-server.sh` - Docker launcher script
- `Dockerfile` - Server container definition
- `requirements.txt` - Python dependencies
- `ui_server.py` - Web UI server
- `server.py` - Console-only server
- `templates/index.html` - Web interface

## Features

- Real-time web dashboard
- Server-Sent Events (SSE) streaming
- Console logging
- Auto-generates protobuf files
