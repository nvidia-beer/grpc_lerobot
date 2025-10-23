#!/usr/bin/env python3
"""
Generic Robot gRPC Client - Collects data from robot via teleoperator interface and streams to server
"""

import grpc
import time
import sys
import logging
import yaml
import importlib
import numpy as np
from pathlib import Path

# Import generated protobuf code
import robot_data_pb2
import robot_data_pb2_grpc

# Import robot calibration module
from robot_calibrate import RobotCalibrator

# Import debug robot for debug mode
from debug_joints import DebugRobot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RobotClient:
    def __init__(self, config_path='config.yaml', server_address='localhost:50051', calibration_dir=None, debug_active_joints=None):
        """
        Initialize Robot client
        
        Args:
            config_path: Path to robot configuration file
            server_address: gRPC server address
            calibration_dir: Path to calibration directory (defaults to ./calibration)
            debug_active_joints: List of joint names that should move in debug mode (None/empty = no debug mode, connects to real hardware)
        """
        self.server_address = server_address
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.robot = None
        self.device_id = self.config.get('device_id', 'robot_unknown')
        self.calibration_dir = Path(calibration_dir) if calibration_dir else Path(__file__).parent / 'calibration'
        self.debug_active_joints = debug_active_joints
    
    # ===== Logging Helper Functions =====
    
    def _log_joint_ranges(self, joint_ranges):
        """Log detected joint ranges"""
        logger.info(f"Joint ranges from SO101Leader.calibration:")
        for joint, (min_v, max_v) in joint_ranges.items():
            logger.info(f"  {joint}: [{min_v}, {max_v}]")
    
    def _log_calibration_details(self):
        """Log all calibration data for each motor to help identify patterns"""
        logger.info("=" * 70)
        logger.info("MOTOR CALIBRATION DATA:")
        logger.info("=" * 70)
        
        for motor_name, motor_calib in self.robot.calibration.items():
            logger.info(f"\n{motor_name}:")
            logger.info(f"  id:            {motor_calib.id if hasattr(motor_calib, 'id') else 'N/A'}")
            logger.info(f"  drive_mode:    {motor_calib.drive_mode if hasattr(motor_calib, 'drive_mode') else 'N/A'}")
            logger.info(f"  homing_offset: {motor_calib.homing_offset if hasattr(motor_calib, 'homing_offset') else 'N/A'}")
            logger.info(f"  range_min:     {motor_calib.range_min if hasattr(motor_calib, 'range_min') else 'N/A'}")
            logger.info(f"  range_max:     {motor_calib.range_max if hasattr(motor_calib, 'range_max') else 'N/A'}")
            
            # Calculate range span
            if hasattr(motor_calib, 'range_min') and hasattr(motor_calib, 'range_max'):
                span = motor_calib.range_max - motor_calib.range_min
                logger.info(f"  range_span:    {span}")
        
        logger.info("\n" + "=" * 70)
    
    def _log_raw_action_values(self, state_dict):
        """Log raw action values from get_action() to identify actual output ranges"""
        logger.info("=" * 70)
        logger.info("RAW ACTION VALUES FROM get_action():")
        logger.info("=" * 70)
        
        # Handle RobotState dataclass
        if hasattr(state_dict, '__dict__'):
            state_dict = vars(state_dict)
        
        if isinstance(state_dict, dict):
            for key, value in sorted(state_dict.items()):
                logger.info(f"  {key:20s} = {value}")
        
        logger.info("=" * 70)
        logger.info("TIP: Compare these values with calibration data above")
        logger.info("     to understand how SO101Leader converts raw servo")
        logger.info("     positions to output values.")
        logger.info("=" * 70 + "\n")
    
    def _log_connection_error(self, error):
        """Log connection error with details"""
        logger.error("=" * 70)
        logger.error("❌ DEVICE CONNECTION FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {error}")
    
    def _log_initialization_error(self, error):
        """Log initialization error with details"""
        logger.error("=" * 70)
        logger.error("❌ ROBOT INITIALIZATION FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {error}")
    
    def _log_grpc_error(self, error):
        """Log gRPC error with details"""
        logger.error("=" * 70)
        logger.error("❌ gRPC CONNECTION ERROR")
        logger.error("=" * 70)
        logger.error(f"Error Code: {error.code()}")
        logger.error(f"Details: {error.details()}")
    
    def _log_unexpected_error(self, error):
        """Log unexpected error with details"""
        logger.error("=" * 70)
        logger.error("❌ UNEXPECTED ERROR")
        logger.error("=" * 70)
        logger.error(f"Error: {error}")
        
    def load_config(self, config_path):
        """Load robot configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            sys.exit(1)
    
    def connect_device(self):
        """Connect to robot device using teleoperator interface"""
        try:
            # Use debug robot if debug mode enabled
            if self.debug_active_joints is not None:
                self.robot = DebugRobot(
                    device_id=self.device_id,
                    calibration_dir=self.calibration_dir,
                    active_joints=self.debug_active_joints
                )
                self.robot.connect()
                
                # Log all calibration data to help identify motor patterns
                self._log_calibration_details()
                
                return True
            
            robot_config = self.config.get('robot', {})
            robot_type = robot_config.get('type', 'unknown')
            
            logger.info(f"Connecting to {robot_type} robot...")
            
            # Get initialization parameters
            init_params = robot_config.get('params', {})
            
            # Import the appropriate robot/teleoperator config class based on robot_type
            config_class = None
            is_teleoperator = False
            
            try:
                # Try teleoperators module (e.g., so101_leader, koch_leader)
                teleop_module = importlib.import_module(f"lerobot.teleoperators.{robot_type}")
                # Find the config class (should end with 'Config')
                config_classes = [name for name in dir(teleop_module) if name.endswith('Config') and not name.startswith('_')]
                if not config_classes:
                    raise AttributeError(f"No Config class found in module")
                config_class_name = config_classes[0]
                config_class = getattr(teleop_module, config_class_name)
                is_teleoperator = True
                logger.info(f"Using teleoperator: {config_class_name}")
            except (ImportError, AttributeError):
                try:
                    # Try robots module (e.g., so101_follower, koch_follower)
                    robot_module = importlib.import_module(f"lerobot.robots.{robot_type}")
                    # Find the config class (should end with 'Config')
                    config_classes = [name for name in dir(robot_module) if name.endswith('Config') and not name.startswith('_')]
                    if not config_classes:
                        raise AttributeError(f"No Config class found in module")
                    config_class_name = config_classes[0]
                    config_class = getattr(robot_module, config_class_name)
                    is_teleoperator = False
                    logger.info(f"Using robot: {config_class_name}")
                except (ImportError, AttributeError) as e:
                    logger.error(f"Failed to import robot type '{robot_type}': {e}")
                    logger.error("Make sure the robot_type is valid (e.g., so101_leader, so101_follower, koch_leader, etc.)")
                    return False
            
            # Add calibration_dir and device_id to parameters
            init_params['id'] = self.device_id
            if hasattr(self, 'calibration_dir'):
                init_params['calibration_dir'] = self.calibration_dir
            
            # Filter parameters to only include those accepted by the config class
            import inspect
            config_sig = inspect.signature(config_class.__init__)
            valid_params = {k: v for k, v in init_params.items() if k in config_sig.parameters}
            
            logger.info(f"Initializing with parameters: {list(valid_params.keys())}")
            
            # Create robot configuration
            robot_cfg = config_class(**valid_params)
            
            # Create robot/teleoperator instance using the appropriate factory
            if is_teleoperator:
                from lerobot.teleoperators import make_teleoperator_from_config
                self.robot = make_teleoperator_from_config(robot_cfg)
            else:
                from lerobot.robots import make_robot_from_config  
                self.robot = make_robot_from_config(robot_cfg)
            
            # Connect to robot
            self.robot.connect()
            
            logger.info(f"Successfully connected to {robot_type} robot")
            
            # Log all calibration data to help identify motor patterns
            self._log_calibration_details()
            
            return True
            
        except ConnectionError as e:
            self._log_connection_error(e)
            self._print_connection_troubleshooting()
            return False
            
        except Exception as e:
            self._log_initialization_error(e)
            import traceback
            traceback.print_exc()
            return False
    
    def _print_connection_troubleshooting(self):
        """Run automatic diagnostics for connection issues"""
        print("\n" + "╔" + "═" * 68 + "╗")
        print("║" + " " * 20 + "🔍 TROUBLESHOOTING GUIDE" + " " * 24 + "║")
        print("╚" + "═" * 68 + "╝")
        
        try:
            import serial
            import serial.tools.list_ports
            
            all_ports = list(serial.tools.list_ports.comports())
            
            if not all_ports:
                print("\n❌ NO USB DEVICES DETECTED")
                print("\n📋 Check the following:")
                print("   1. Robot arm is powered on")
                print("   2. USB cable is securely connected")
                print("   3. If using WSL2 (Windows), attach USB device:")
                print("      • Open PowerShell as Administrator")
                print("      • Run: usbipd list")
                print("      • Run: usbipd attach --wsl --busid X-X")
                print("   4. If using Docker, ensure USB device is mounted")
                print("      • Check -v /dev/bus/usb:/dev/bus/usb flag")
                print("\n" + "─" * 70 + "\n")
                return
            
            print("\n📱 DETECTED SERIAL PORTS:\n")
            
            test_ports = [p for p in all_ports if 'ttyACM' in p.device or 'ttyUSB' in p.device]
            robot_ports = []
            
            for port in all_ports:
                try:
                    with serial.Serial(port.device, 9600, timeout=1) as ser:
                        status = "✅ Available"
                        if 'ttyACM' in port.device or 'ttyUSB' in port.device:
                            robot_ports.append(port.device)
                        print(f"   {status:20} {port.device}")
                        if port.description:
                            print(f"      └─ {port.description}")
                except PermissionError:
                    print(f"   ❌ Permission Denied  {port.device}")
                    print(f"      └─ Fix: sudo chmod 666 {port.device}")
                    print(f"      └─ Or: sudo usermod -a -G dialout $USER")
                    print(f"             (then logout and login)")
                except Exception as e:
                    print(f"   ⚠️  Busy/In Use        {port.device}")
                    print(f"      └─ {str(e)[:60]}")
            
            print("\n📝 NEXT STEPS:")
            if robot_ports:
                print(f"   • Update config.yaml to use port: {robot_ports[0]}")
                print(f"   • Or run: lerobot-find-port")
            else:
                print("   • No likely robot ports found (looking for ttyACM*/ttyUSB*)")
                print("   • If robot is connected, check cable and power")
                print("   • Try: lsusb (to see all USB devices)")
            
            print("\n" + "─" * 70 + "\n")
            
        except ImportError:
            print("\n❌ Python 'pyserial' module not installed")
            print("   Fix: pip install pyserial")
            print("\n" + "─" * 70 + "\n")
    
    def _print_grpc_troubleshooting(self, error):
        """Print troubleshooting information for gRPC connection errors"""
        print("\n" + "╔" + "═" * 68 + "╗")
        print("║" + " " * 20 + "🔍 gRPC TROUBLESHOOTING" + " " * 25 + "║")
        print("╚" + "═" * 68 + "╝")
        
        error_code = error.code()
        
        if error_code == grpc.StatusCode.UNAVAILABLE:
            print("\n❌ SERVER UNAVAILABLE")
            print(f"\n📋 The server at {self.server_address} is not reachable.\n")
            print("   Possible causes:")
            print("   1. Server is not running")
            print("      • Check if the gRPC server is started")
            print("      • Verify server logs for errors")
            print("")
            print("   2. Wrong server address")
            print(f"      • Current: {self.server_address}")
            print("      • Check server IP and port")
            print("")
            print("   3. Network/firewall issues")
            print("      • Test connectivity: ping <server-ip>")
            print("      • Check firewall allows port 50051")
            print("      • If using Docker, verify --network=host flag")
            
        elif error_code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print("\n❌ CONNECTION TIMEOUT")
            print("\n📋 Server took too long to respond.\n")
            print("   • Server may be overloaded")
            print("   • Network latency is too high")
            print("   • Check server performance and network connection")
            
        elif error_code == grpc.StatusCode.UNAUTHENTICATED:
            print("\n❌ AUTHENTICATION FAILED")
            print("\n📋 Server requires authentication.\n")
            print("   • Check if authentication credentials are configured")
            print("   • Verify API keys or tokens")
            
        else:
            print(f"\n❌ ERROR: {error_code}")
            print("\n📋 General troubleshooting:\n")
            print("   • Check server logs for details")
            print(f"   • Verify server address: {self.server_address}")
            print("   • Test network connectivity")
        
        print("\n" + "─" * 70 + "\n")
    
    def get_joint_ranges(self):
        """Get joint action ranges from robot's calibration."""
        if hasattr(self, '_joint_ranges_cache'):
            return self._joint_ranges_cache
        
        # SO101Leader calibration: dict of motor_name -> MotorCalibration object
        # The calibration contains:
        # - range_min, range_max: Raw servo position values (e.g., 2029-3265) - hardware limits
        # - drive_mode: Motor control mode (0=extended position, 1=position control)
        # - homing_offset: Servo offset for zero position
        # 
        # SO101Leader internally converts raw servo positions (range_min to range_max) 
        # to normalized output values. Based on LeRobot conventions:
        # - Regular joints (bidirectional): -100 to 100
        # - Gripper (unidirectional): 0 to 100
        #
        # The drive_mode field may indicate control mode but doesn't directly determine output range.
        # We need to infer the output range based on joint type/name.
        joint_ranges = {}
        for motor_name, motor_calib in self.robot.calibration.items():
            # Gripper is typically unidirectional (0 to 100)
            if 'gripper' in motor_name.lower():
                joint_ranges[motor_name] = (0.0, 100.0)
            else:
                # All other joints are bidirectional (-100 to 100)
                joint_ranges[motor_name] = (-100.0, 100.0)
        
        self._joint_ranges_cache = joint_ranges
        self._log_joint_ranges(joint_ranges)
        return joint_ranges
    
    def normalize_to_01(self, flat_state):
        """
        Normalize LeRobot values to [0.0, 1.0] range.
        
        LeRobot typically returns:
        - Regular joints: -100 to 100
        - Gripper: 0 to 100
        
        This converts everything to [0.0, 1.0] for consistency.
        """
        joint_ranges = self.get_joint_ranges()
        normalized = {}
        
        for key, value in flat_state.items():
            # Extract joint name from key (e.g., "shoulder_pan.pos" -> "shoulder_pan")
            joint_name = key.split('.')[0] if '.' in key else key
            
            # Get expected range for this joint
            if joint_name in joint_ranges:
                min_val, max_val = joint_ranges[joint_name]
            else:
                # Unknown joint - assume bidirectional [-100, 100]
                min_val, max_val = -100.0, 100.0
            
            # Normalize: (value - min) / (max - min)
            if max_val != min_val:
                normalized_value = (value - min_val) / (max_val - min_val)
                # Clamp to [0, 1]
                normalized[key] = max(0.0, min(1.0, float(normalized_value)))
            else:
                normalized[key] = 0.5
        
        return normalized
    
    def read_device_state(self):
        """Read current state from robot device and normalize to [0, 1]"""
        try:
            # Get action from robot (works for both real and mock robots)
            if hasattr(self.robot, 'get_action'):
                state_dict = self.robot.get_action()
            elif hasattr(self.robot, 'read'):
                state_dict = self.robot.read()
            else:
                raise AttributeError(f"Robot {type(self.robot).__name__} has neither 'get_action' nor 'read' method")
            
            # Log raw values from first reading to help identify ranges
            if not hasattr(self, '_logged_raw_values'):
                self._log_raw_action_values(state_dict)
                self._logged_raw_values = True
            
            # Convert state to flat dictionary for protobuf
            flat_state = {}
            
            # Handle RobotState dataclass (from mock or real teleoperator)
            if hasattr(state_dict, '__dict__'):
                # Convert dataclass to dictionary
                state_dict = vars(state_dict)
            
            # Flatten nested structures and convert to float
            if isinstance(state_dict, dict):
                for key, value in state_dict.items():
                    if isinstance(value, (list, tuple)):
                        # Convert lists to indexed keys
                        for idx, val in enumerate(value):
                            flat_state[f"{key}_{idx}"] = float(val)
                    elif isinstance(value, (int, float)):
                        flat_state[key] = float(value)
                    elif hasattr(value, '__iter__') and not isinstance(value, str):
                        # Handle numpy arrays and similar iterables
                        for idx, val in enumerate(value):
                            flat_state[f"{key}_{idx}"] = float(val)
                    else:
                        # Try to convert to float
                        try:
                            flat_state[key] = float(value)
                        except:
                            pass
            
            # Normalize LeRobot values to [0, 1]
            normalized_state = self.normalize_to_01(flat_state)
            
            # Create reading message
            reading = robot_data_pb2.RobotReading(
                timestamp=time.time(),
                robot_type=self.config.get('robot', {}).get('type', 'unknown'),
                device_id=self.device_id,
                state=normalized_state
            )
            
            return reading
            
        except Exception as e:
            logger.error(f"Error reading device state: {e}")
            return None
    
    def generate_readings(self, rate_hz=30):
        """Generator that yields robot readings at specified rate"""
        interval = 1.0 / rate_hz
        reading_count = 0
        
        while True:
            try:
                start_time = time.time()
                
                reading = self.read_device_state()
                if reading:
                    reading_count += 1
                    if reading_count % 30 == 0:  # Log every 30 readings (1 second at 30Hz)
                        logger.info(f"Generated {reading_count} readings")
                    yield reading
                
                # Maintain consistent rate
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except KeyboardInterrupt:
                logger.info("Stopping data collection...")
                break
            except Exception as e:
                logger.error(f"Error in reading loop: {e}")
                time.sleep(1)  # Wait before retrying
    
    def stream_to_server(self, rate_hz=30):
        """Stream robot data to gRPC server"""
        logger.info(f"Connecting to gRPC server at {self.server_address}...")
        
        try:
            # Create gRPC channel
            with grpc.insecure_channel(self.server_address) as channel:
                stub = robot_data_pb2_grpc.RobotDataStreamStub(channel)
                
                logger.info("Connected to gRPC server. Starting data stream...")
                
                # Stream data to server
                responses = stub.StreamData(self.generate_readings(rate_hz))
                
                logger.info("Waiting for server responses...")
                # Process responses
                for response in responses:
                    if response.success:
                        logger.debug(f"Server response: {response.message}")
                    else:
                        logger.warning(f"Server error: {response.message}")
                        
        except grpc.RpcError as e:
            self._log_grpc_error(e)
            self._print_grpc_troubleshooting(e)
        except Exception as e:
            self._log_unexpected_error(e)
            import traceback
            traceback.print_exc()
        finally:
            self.disconnect_device()
    
    def disconnect_device(self):
        """Disconnect from robot device"""
        if self.robot:
            try:
                # Check if robot is connected before attempting to disconnect
                if hasattr(self.robot, 'is_connected') and callable(self.robot.is_connected):
                    if self.robot.is_connected():
                        self.robot.disconnect()
                        logger.info("Disconnected from robot device")
                    else:
                        logger.info("Robot already disconnected")
                else:
                    # If no is_connected method, just try to disconnect
                    self.robot.disconnect()
                    logger.info("Disconnected from robot device")
            except Exception as e:
                # Ignore errors about already being disconnected
                error_msg = str(e).lower()
                if 'not connected' in error_msg or 'already disconnected' in error_msg:
                    logger.info("Robot already disconnected")
                else:
                    logger.error(f"Error disconnecting device: {e}")
    
    def validate_calibration(self):
        """
        Check if calibration folder exists and contains calibration files.
        If not, run calibration.
        
        Returns:
            bool: True if calibration exists or was created successfully, False otherwise
        """
        # Skip calibration check for debug robot
        if isinstance(self.robot, DebugRobot):
            logger.info("Debug robot: Calibration loaded from file")
            return True
        
        # Check if calibration directory exists
        if not self.calibration_dir.exists():
            logger.warning(f"Calibration directory not found: {self.calibration_dir}")
            logger.info("Running calibration...")
            return self._run_calibration()
        
        # Check if calibration directory has any files
        calibration_files = list(self.calibration_dir.glob('*'))
        if not calibration_files:
            logger.warning(f"Calibration directory is empty: {self.calibration_dir}")
            logger.info("Running calibration...")
            return self._run_calibration()
        
        logger.info(f"✅ Calibration found: {len(calibration_files)} file(s)")
        return True
    
    def _run_calibration(self):
        """
        Run calibration using robot_calibrate module
        
        Returns:
            bool: True if calibration successful, False otherwise
        """
        try:
            calibrator = RobotCalibrator(
                calibration_dir=str(self.calibration_dir),
                config_path=self.config_path
            )
            
            result = calibrator.run_calibration(force=False)
            
            if result:
                logger.info("✅ Calibration completed successfully")
            else:
                logger.error("❌ Calibration failed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during calibration: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Robot gRPC Client - Stream robot data to server')
    parser.add_argument('--config', default='config.yaml', help='Robot configuration file')
    parser.add_argument('--server', default='localhost:50051', help='gRPC server address')
    parser.add_argument('--rate', type=int, default=30, help='Sampling rate in Hz')
    parser.add_argument('--calibration', default=None, help='Calibration directory path (default: ./calibration)')
    parser.add_argument('--debug-joints', nargs='+', default=None, 
                        help='Enable debug mode and specify joint names to move (e.g., --debug-joints gripper shoulder_pan). If not specified, connects to real hardware.')
    
    args = parser.parse_args()
    
    # Create client
    client = RobotClient(
        config_path=args.config, 
        server_address=args.server, 
        calibration_dir=args.calibration, 
        debug_active_joints=args.debug_joints
    )
    
    # Validate calibration exists (or create it)
    if not client.validate_calibration():
        logger.error("Calibration validation failed. Cannot proceed.")
        sys.exit(1)
    
    # Connect to device
    if not client.connect_device():
        logger.error("Failed to connect to device")
        sys.exit(1)
    
    # Stream data
    try:
        client.stream_to_server(rate_hz=args.rate)
    except KeyboardInterrupt:
        logger.info("Shutting down client...")
    finally:
        client.disconnect_device()


if __name__ == '__main__':
    main()
