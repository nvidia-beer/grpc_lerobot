#!/usr/bin/env python3
"""
Robot gRPC Server with Web UI - Receives data and displays in web browser
"""

import grpc
from concurrent import futures
import threading
import logging
import json
import time
from flask import Flask, render_template, Response
from datetime import datetime

# Import base server components
from server import RobotDataStreamServicer as BaseServicer
import robot_data_pb2
import robot_data_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global storage for latest data
latest_data = {
    'timestamp': None,
    'robot_type': None,
    'device_id': None,
    'state': {},  # Normalized state values [0.0, 1.0]
    'connection_status': 'Waiting for connection...'
}
data_lock = threading.Lock()

# Flask app for web interface
app = Flask(__name__)


class UIRobotDataStreamServicer(BaseServicer):
    """Extended gRPC service with UI data storage"""
    
    def StreamData(self, request_iterator, context):
        """Handle streaming robot data and update UI state"""
        logger.info("Client connected to stream")
        
        try:
            for reading in request_iterator:
                # Update global data for UI
                with data_lock:
                    latest_data['timestamp'] = reading.timestamp
                    latest_data['robot_type'] = reading.robot_type
                    latest_data['device_id'] = reading.device_id
                    latest_data['state'] = dict(reading.state)
                    latest_data['connection_status'] = 'Connected'
                
                # Log received data
                timestamp_str = datetime.fromtimestamp(
                    reading.timestamp
                ).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                logger.info(f"Received from {reading.robot_type} (ID: {reading.device_id})")
                logger.info(f"  Timestamp: {timestamp_str}")
                logger.info(f"  State ({len(reading.state)} values, normalized to [0, 1])")
                
                # Send acknowledgment
                response = robot_data_pb2.RobotResponse(
                    success=True,
                    message=f"Received data with {len(reading.state)} state values"
                )
                yield response
                
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            with data_lock:
                latest_data['connection_status'] = f'Error: {str(e)}'
        finally:
            logger.info("Client disconnected from stream")
            with data_lock:
                latest_data['connection_status'] = 'Disconnected'


@app.route('/')
def index():
    """Serve main web page"""
    return render_template('index.html')


@app.route('/data')
def get_data():
    """API endpoint for latest data"""
    with data_lock:
        data_copy = latest_data.copy()
        
    # Add human-readable timestamp
    if data_copy['timestamp']:
        data_copy['timestamp_str'] = datetime.fromtimestamp(
            data_copy['timestamp']
        ).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    else:
        data_copy['timestamp_str'] = 'N/A'
    
    return json.dumps(data_copy)


@app.route('/stream')
def stream():
    """Server-Sent Events stream for real-time updates"""
    def generate():
        last_timestamp = None
        while True:
            with data_lock:
                current_timestamp = latest_data.get('timestamp')
                
                # Only send if data has changed
                if current_timestamp != last_timestamp:
                    data_copy = latest_data.copy()
                    if data_copy['timestamp']:
                        data_copy['timestamp_str'] = datetime.fromtimestamp(
                            data_copy['timestamp']
                        ).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    else:
                        data_copy['timestamp_str'] = 'N/A'
                    
                    yield f"data: {json.dumps(data_copy)}\n\n"
                    last_timestamp = current_timestamp
            
            time.sleep(0.03)  # ~30 Hz update rate
    
    return Response(generate(), mimetype='text/event-stream')


def serve_grpc(port=50051):
    """Start gRPC server with UI servicer"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    robot_data_pb2_grpc.add_RobotDataStreamServicer_to_server(
        UIRobotDataStreamServicer(), server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"gRPC server started on port {port}")
    return server


def serve_web(host='0.0.0.0', port=8080):
    """Start Flask web server"""
    logger.info(f"Web UI available at http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Robot gRPC Server with Web UI')
    parser.add_argument('--grpc-port', type=int, default=50051, help='gRPC port (default: 50051)')
    parser.add_argument('--web-port', type=int, default=8080, help='Web server port (default: 8080)')
    parser.add_argument('--host', default='0.0.0.0', help='Web server host (default: 0.0.0.0)')
    args = parser.parse_args()
    
    # Start gRPC server in background
    grpc_server = serve_grpc(port=args.grpc_port)
    
    try:
        # Start web server (blocking)
        serve_web(host=args.host, port=args.web_port)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        grpc_server.stop(0)


if __name__ == '__main__':
    main()
