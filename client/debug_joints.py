#!/usr/bin/env python3
"""
Debug Robot for Debug Mode - Simulates robot behavior without hardware
"""

import time
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DebugRobot:
    """Debug robot that simulates SO101Leader behavior for testing without hardware"""
    
    def __init__(self, device_id, calibration_dir, active_joints=None):
        """
        Initialize debug robot
        
        Args:
            device_id: Robot device identifier
            calibration_dir: Path to calibration directory
            active_joints: List of joint names that should move (None = all static)
        """
        self.device_id = device_id
        self.calibration_dir = Path(calibration_dir)
        self.active_joints = active_joints or []
        self.start_time = None
        self.calibration = None
        
        logger.info(f"🐛 Debug Robot initialized - Active joints: {', '.join(self.active_joints) if self.active_joints else 'None (all static)'}")
    
    def connect(self):
        """Simulate robot connection"""
        self.start_time = time.time()
        self._load_calibration()
        logger.info("Debug robot connected")
    
    def disconnect(self):
        """Simulate robot disconnection"""
        logger.info("Debug robot disconnected")
    
    def is_connected(self):
        """Check if debug robot is connected"""
        return self.start_time is not None
    
    def _load_calibration(self):
        """Load calibration data - format matching real SO101Leader"""
        import json
        from types import SimpleNamespace
        
        calib_file = self.calibration_dir / f"{self.device_id}.json"
        
        if not calib_file.exists():
            raise RuntimeError(f"Debug mode requires calibration file: {calib_file}")
        
        with open(calib_file, 'r') as f:
            calib_data = json.load(f)
        
        # Create calibration dict: motor_name -> MotorCalibration object
        # Matching real SO101Leader format
        self.calibration = {}
        for motor_name, motor_config in calib_data.items():
            # Create mock MotorCalibration object with drive_mode
            self.calibration[motor_name] = SimpleNamespace(
                id=motor_config.get('id', 0),
                drive_mode=motor_config.get('drive_mode', 0),  # 0 = bidirectional
                homing_offset=motor_config.get('homing_offset', 0),
                range_min=motor_config.get('range_min', 0),
                range_max=motor_config.get('range_max', 4096)
            )
        
        logger.info(f"Debug calibration loaded: {len(self.calibration)} joints")
    
    def get_action(self):
        """Generate simulated robot action data"""
        if not self.is_connected():
            raise RuntimeError("Debug robot not connected")
        
        t = time.time() - self.start_time
        state_dict = {}
        
        for i, (motor_name, motor_calib) in enumerate(self.calibration.items()):
            # Assume SO101Leader outputs -100 to 100 for all joints
            # (Without source code access, we can't verify individual joint ranges)
            start, end = -100.0, 100.0
            
            # Check if this joint should be active (moving)
            is_active = motor_name in self.active_joints
            
            if is_active:
                # Generate sinusoidal motion for active joints
                freq = 0.15 + i * 0.03
                phase = i * (2 * np.pi / len(self.calibration))
                sin_value = np.sin(2 * np.pi * freq * t + phase)
                
                # Map to action range
                center = (start + end) / 2
                amplitude = (end - start) / 2
                position = center + amplitude * sin_value
            else:
                # Keep inactive joints at center position
                position = (start + end) / 2
            
            state_dict[f"{motor_name}.pos"] = float(position)
        
        return state_dict

