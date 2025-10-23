#!/usr/bin/env python3
"""
Generic Robot Calibration Module

Handles calibration for any robot type using lerobot API and configuration files.
"""

import logging
import yaml
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)


class RobotCalibrator:
    """Generic calibrator for any robot using lerobot"""
    
    def __init__(self, calibration_dir=None, config_path=None):
        """
        Initialize robot calibrator
        
        Args:
            calibration_dir: Directory for calibration files (default: ./calibration)
            config_path: Path to robot configuration YAML file (optional)
        """
        if calibration_dir is None:
            self.calibration_dir = Path(__file__).parent / 'calibration'
        else:
            self.calibration_dir = Path(calibration_dir)
        
        # Create calibration directory if it doesn't exist
        self.calibration_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Calibration directory: {self.calibration_dir}")
        
        # Load config if provided
        self.config = None
        if config_path:
            self.config = self.load_config(config_path)
    
    def load_config(self, config_path):
        """Load robot configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return None
    
    def check_calibration(self, robot_id):
        """
        Check if calibration files exist for the robot
        
        Args:
            robot_id: Unique identifier for the robot
            
        Returns:
            bool: True if calibration exists, False otherwise
        """
        # Look for calibration file (typically named {robot_id}.json or similar)
        calibration_files = list(self.calibration_dir.glob(f"*{robot_id}*"))
        
        if calibration_files:
            logger.info(f"Found calibration files: {[f.name for f in calibration_files]}")
            return True
        else:
            logger.warning(f"No calibration files found for robot '{robot_id}' in {self.calibration_dir}")
            return False
    
    def run_calibration(self, robot_type=None, port=None, robot_id=None, force=False):
        """
        Run robot calibration using lerobot API
        
        Args:
            robot_type: Type of robot (e.g., so101_leader, koch, etc.). If None, uses config.
            port: Serial port for the robot (e.g., /dev/ttyACM0). If None, uses config.
            robot_id: Unique identifier for the robot. If None, uses device_id from config.
            force: Force recalibration even if calibration exists
            
        Returns:
            bool: True if calibration successful, False otherwise
        """
        # Use config if parameters not provided
        if self.config:
            robot_config = self.config.get('robot', {})
            robot_type = robot_type or robot_config.get('type')
            port = port or robot_config.get('params', {}).get('port')
            robot_id = robot_id or self.config.get('device_id', 'robot_unknown')
        
        # Validate required parameters
        if not robot_type or not port or not robot_id:
            logger.error("Missing required parameters: robot_type, port, and robot_id must be provided")
            return False
        
        # Check if lerobot is available
        try:
            import lerobot
            logger.info(f"Using lerobot v{lerobot.__version__} for calibration")
        except ImportError:
            logger.error("lerobot package not found. Cannot run calibration.")
            logger.info("Install lerobot with: pip install lerobot")
            return False
        
        # Check existing calibration
        if not force and self.check_calibration(robot_id):
            response = input("Calibration already exists. Recalibrate? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                logger.info("Using existing calibration")
                return True
        
        logger.info(f"Starting calibration for {robot_type} (ID: {robot_id})...")
        logger.info(f"Port: {port}")
        logger.info(f"Calibration directory: {self.calibration_dir}")
        
        try:
            logger.info(f"Calibrating {robot_type}...")
            
            # Import the appropriate robot/teleoperator class based on robot_type
            # Try importing from teleoperators first (for leader arms), then from robots (for followers)
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
            
            logger.info("Please follow the on-screen instructions for calibration...")
            logger.info("Move the arm to the required positions when prompted.")
            
            # Create robot configuration
            robot_cfg = config_class(
                port=port,
                id=robot_id,
                calibration_dir=self.calibration_dir
            )
            
            # Create robot/teleoperator instance using the appropriate factory
            if is_teleoperator:
                from lerobot.teleoperators import make_teleoperator_from_config
                robot = make_teleoperator_from_config(robot_cfg)
            else:
                from lerobot.robots import make_robot_from_config  
                robot = make_robot_from_config(robot_cfg)
            
            # Connect to robot
            logger.info("Connecting to robot...")
            robot.connect()
            
            # Run calibration
            robot.calibrate()
            
            logger.info("✅ Calibration completed successfully")
            
            # Disconnect robot after calibration
            robot.disconnect()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Calibration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    


def main():
    """CLI for running robot calibration"""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Generic Robot Calibration')
    parser.add_argument('--config', default='config.yaml', help='Path to robot configuration file')
    parser.add_argument('--type', help='Robot type (overrides config)')
    parser.add_argument('--port', help='Serial port (overrides config)')
    parser.add_argument('--id', help='Robot ID (overrides config)')
    parser.add_argument('--calibration-dir', default=None, help='Calibration directory')
    parser.add_argument('--force', action='store_true', help='Force recalibration')
    parser.add_argument('--check-only', action='store_true', help='Only check if calibration exists')
    
    args = parser.parse_args()
    
    calibrator = RobotCalibrator(
        calibration_dir=args.calibration_dir,
        config_path=args.config
    )
    
    # Determine robot_id for check-only mode
    robot_id = args.id
    if not robot_id and calibrator.config:
        robot_id = calibrator.config.get('device_id', 'robot_unknown')
    
    if args.check_only:
        if not robot_id:
            logger.error("Robot ID is required for check-only mode")
            return 1
            
        if calibrator.check_calibration(robot_id):
            logger.info("✅ Calibration exists")
            return 0
        else:
            logger.warning("❌ Calibration not found")
            return 1
    
    if calibrator.run_calibration(
        robot_type=args.type,
        port=args.port,
        robot_id=args.id,
        force=args.force
    ):
        logger.info("✅ Calibration completed successfully")
        return 0
    else:
        logger.error("❌ Calibration failed")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

