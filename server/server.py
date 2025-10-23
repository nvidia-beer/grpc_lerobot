#!/usr/bin/env python3
"""
Simple Robot gRPC Server - Receives data and logs to console
"""

import grpc
from concurrent import futures
import logging
from datetime import datetime

# Import generated protobuf code
import robot_data_pb2
import robot_data_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RobotDataStreamServicer(robot_data_pb2_grpc.RobotDataStreamServicer):
    """gRPC service implementation"""
    
    def StreamData(self, request_iterator, context):
        """Handle streaming robot data"""
        logger.info("Client connected to stream")
        
        try:
            for reading in request_iterator:
                # Convert timestamp to readable format
                timestamp_str = datetime.fromtimestamp(
                    reading.timestamp
                ).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                # Log basic info
                logger.info(f"Received from {reading.robot_type} (ID: {reading.device_id})")
                logger.info(f"  Timestamp: {timestamp_str}")
                
                # Log all state values (normalized to [0, 1])
                state_dict = dict(reading.state)
                logger.info(f"  State ({len(state_dict)} values, normalized to [0, 1]):")
                for key, value in state_dict.items():
                    logger.info(f"    {key}: {value:.4f}")
                
                # Send acknowledgment
                response = robot_data_pb2.RobotResponse(
                    success=True,
                    message=f"Received data with {len(reading.state)} state values"
                )
                yield response
                
        except Exception as e:
            logger.error(f"Error in stream: {e}")
        finally:
            logger.info("Client disconnected from stream")


def serve_grpc(port=50051):
    """Start gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    robot_data_pb2_grpc.add_RobotDataStreamServicer_to_server(
        RobotDataStreamServicer(), server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"gRPC server started on port {port}")
    logger.info("Waiting for clients to connect...")
    return server


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Robot gRPC Server')
    parser.add_argument('--grpc-port', type=int, default=50051, help='gRPC port')
    args = parser.parse_args()
    
    # Start gRPC server
    grpc_server = serve_grpc(port=args.grpc_port)
    
    try:
        # Keep server running
        logger.info("Press Ctrl+C to stop the server")
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        grpc_server.stop(0)


if __name__ == '__main__':
    main()

