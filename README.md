# 🤖 gRPC LeRobot

Remote control and monitoring system for SO-101 Leader Arm. Stream real-time robot data from hardware to a remote server with a web-based dashboard.

<div align="center">

[![gRPC](https://img.shields.io/badge/gRPC-Protocol-blue)](https://grpc.io/)
[![Python](https://img.shields.io/badge/Python-3.8+-green)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

</div>

---

## 📋 Overview

This project enables remote teleoperation and data collection from LeRobot SO-101 Leader Arms:

<table>
<tr>
<td width="33%">

### 🖥️ gRPC Server
Receives and displays robot data via web dashboard with real-time updates

</td>
<td width="33%">

### 📡 gRPC Client
Reads from robot hardware and streams calibrated joint positions

</td>
<td width="33%">

### 🌐 Web UI
Beautiful real-time visualization with Server-Sent Events

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Start the Server

```bash
# Default ports (gRPC: 50051, Web: 8070)
./grpc-lerobot-server.sh

# Custom ports
./grpc-lerobot-server.sh 50052 8080
```

> **🌐 Access the web dashboard at:** http://localhost:8070

### Start the Client

```bash
# Connect to local server
./grpc-lerobot-client.sh

# Connect to remote server
./grpc-lerobot-client.sh --server 192.168.1.100:50051

# Run without hardware (debug mode with simulated joints)
./grpc-lerobot-client.sh --debug-joints gripper shoulder_pan elbow
```

> **✅ What happens:** Loads calibration, connects to robot at `/dev/ttyACM0`, streams at 30 Hz  
> **🧪 Debug mode:** Simulates robot data for testing without hardware (specify which joints should move)

---

## 🦾 Robot Setup

### Linux / WSL2

```bash
# Check USB device
ls -la /dev/ttyACM*

# Set permissions
sudo chmod 666 /dev/ttyACM0

# Add user to dialout group (one-time)
sudo usermod -a -G dialout $USER
```

> **⚠️ Important:** After adding to dialout group, restart WSL2:
> ```bash
> wsl --shutdown  # In Windows PowerShell
> ```

### Windows USB/IP Setup

<details>
<summary><b>📦 Step 1: Install usbipd (PowerShell as Administrator)</b></summary>

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

</details>

<details>
<summary><b>🔌 Step 2: Attach USB device</b></summary>

```powershell
# List devices
usbipd list

# Attach (replace 4-4 with your BUSID)
usbipd attach --wsl --busid 4-4

# Verify
usbipd list
```

**Example output:**
```
BUSID  VID:PID    DEVICE                                    STATE
4-4    1a86:55d3  USB-Enhanced-SERIAL CH343 (COM5)         Attached
```

</details>

> **⚠️ Note:** USB device must be re-attached after every WSL2 restart.

---

## ⚙️ Configuration

### Server Options

```bash
./grpc-lerobot-server.sh [GRPC_PORT] [WEB_PORT]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GRPC_PORT` | `50051` | gRPC server port |
| `WEB_PORT` | `8070` | Web UI port |

### Client Launcher Options

```bash
./grpc-lerobot-client.sh [--server ADDRESS:PORT] [--debug-joints <joint_names...>]
```

| Option | Description |
|--------|-------------|
| `--server` | gRPC server address:port (default: localhost:50051) |
| `--debug-joints` | Run in debug mode with specified joints moving (no hardware required) |

### Advanced Client Options

```bash
python client/grpc_client.py \
    --config client/config.yaml \
    --server localhost:50051 \
    --rate 30 \
    --calibration ./calibration
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `client/config.yaml` | Robot configuration file |
| `--server` | `localhost:50051` | gRPC server address:port |
| `--rate` | `30` | Sampling rate in Hz |
| `--calibration` | `./calibration` | Calibration directory path |
| `--debug-joints` | - | List of joint names to simulate (enables debug mode, no hardware) |

---

## 🎯 Calibration

Calibrate your robot before first use:

```bash
python client/robot_calibrate.py \
    --config client/config.yaml \
    --output ./calibration
```

This creates calibration files (e.g., `SO101_Leader_1.json`) that map raw motor values to joint angles.

<details>
<summary><b>📊 Example calibration output</b></summary>

```json
{
  "joint_0": { "min": -180, "max": 180 },
  "joint_1": { "min": -90, "max": 90 },
  "joint_2": { "min": -90, "max": 90 },
  "joint_3": { "min": -180, "max": 180 },
  "joint_4": { "min": -90, "max": 90 },
  "joint_5": { "min": -180, "max": 180 }
}
```

</details>

---

## 📁 Project Structure

```
grpc_lerobot/
├── 🖥️  server/                    # gRPC Server + Web UI
│   ├── ui_server.py              # Server with web dashboard
│   ├── server.py                 # Console-only server
│   ├── templates/                # Web UI templates
│   └── docker/                   # Server Docker config
│
├── 📡  client/                    # Robot Client
│   ├── grpc_client.py            # Main client application
│   ├── robot_calibrate.py        # Calibration tool
│   ├── debug_joints.py            # Debug robot for testing
│   ├── config.yaml               # Robot configuration
│   └── docker/                   # Client Docker config
│
├── 🔧  grpc/                      # Protocol Definitions
│   └── robot_data.proto          # gRPC protocol buffers
│
├── 🎯  calibration/               # Calibration Data
│   └── SO101_Leader_1.json       # Joint calibration
│
├── 🚀  grpc-lerobot-server.sh    # Server launcher script
├── 🚀  grpc-lerobot-client.sh    # Client launcher script
└── 📖  README.md                 # This file
```

---

## 🔍 Troubleshooting

<details>
<summary><b>❌ USB Device Not Found</b></summary>

```bash
# Check connection
lsusb
ls -la /dev/ttyACM*

# Check system logs
dmesg | grep tty | tail -20

# WSL2: Re-attach USB (in Windows PowerShell as Administrator)
usbipd attach --wsl --busid 4-4
```

</details>

<details>
<summary><b>❌ Permission Denied</b></summary>

```bash
# Fix permissions
sudo chmod 666 /dev/ttyACM0

# Add to dialout group (requires logout/restart)
sudo usermod -a -G dialout $USER
```

</details>

<details>
<summary><b>❌ Connection Refused</b></summary>

- ✅ Verify server is running: `docker ps | grep grpc-lerobot-server`
- 🌐 Test network connectivity: `ping <server-ip>`
- 🔥 Check firewall rules on both client and server
- 🔌 Ensure correct port (default: 50051)
- 📋 Check server logs: `docker logs grpc-lerobot-server`

</details>

<details>
<summary><b>❌ Calibration Files Not Found</b></summary>

```bash
# Check if calibration directory exists
ls -la ./calibration

# Run calibration
python client/robot_calibrate.py --config client/config.yaml --output ./calibration

# Or specify correct path
./grpc-lerobot-client.sh --calibration /path/to/calib
```

</details>

<details>
<summary><b>❌ High Latency or Dropped Frames</b></summary>

| Issue | Solution | Command |
|-------|----------|---------|
| High sampling rate | Reduce rate | `--rate 10` |
| USB quality | Check connection | `lsusb -v` |
| WSL2 resources | Monitor usage | `htop` |
| Network latency | Check ping | `ping <server-ip>` |

</details>

---

## 🛠️ Development

### Manual Docker Build

<details>
<summary><b>🖥️ Server</b></summary>

```bash
docker build -t grpc-lerobot-server -f server/docker/Dockerfile .

docker run --network=host grpc-lerobot-server \
    python server/ui_server.py --grpc-port 50051 --web-port 8070
```

</details>

<details>
<summary><b>📡 Client</b></summary>

```bash
docker build -t grpc-lerobot-client -f client/docker/Dockerfile .

docker run --privileged --network=host \
    -v /dev/bus/usb:/dev/bus/usb \
    grpc-lerobot-client \
    python client/grpc_client.py --server localhost:50051
```

</details>

### Testing Without Hardware

Use the `--debug-joints` flag to run the client without physical hardware:

```bash
# Using the launcher script (specify which joints should move)
./grpc-lerobot-client.sh --debug-joints gripper shoulder_pan elbow

# Or directly with Python
python client/grpc_client.py \
    --config client/config.yaml \
    --server localhost:50051 \
    --debug-joints gripper shoulder_pan
```

> **Note:** Debug mode requires calibration files to simulate realistic joint ranges. Specify joint names to see movement in the dashboard.

---

## 💬 Support

For issues or questions:

1. 📖 Check the [Troubleshooting](#-troubleshooting) section
2. 📋 Review server logs: `docker logs grpc-lerobot-server`
3. 📋 Review client logs: `docker logs grpc-lerobot-client`
4. 🐛 Open an issue on GitHub

---

<div align="center">

**Built with ❤️ for robotics enthusiasts**

⭐ Star this repo if you find it helpful!

</div>
