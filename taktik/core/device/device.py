import logging
import subprocess
import time
from typing import List, Optional

import uiautomator2 as u2

logger = logging.getLogger(__name__)

class DeviceManager:    
    @staticmethod
    def get_connected_devices() -> List[str]:
        try:
            result = subprocess.run(
                ["adb", "devices"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            lines = result.stdout.strip().split('\n')[1:]
            devices = []
            
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2 and parts[1] == 'device':
                        devices.append(parts[0])
            
            return devices
        except subprocess.SubprocessError as e:
            logger.error(f"Error retrieving devices: {e}")
            return []

    @staticmethod
    def connect_to_device(device_id: str) -> Optional[u2.Device]:
        try:
            device = u2.connect(device_id)
            logger.info(f"Connected to device {device_id}")
            return device
        except Exception as e:
            logger.error(f"Error connecting to device {device_id}: {e}")
            return None

    @staticmethod
    def launch_app(device: u2.Device, package_name: str) -> bool:
        try:
            device.app_start(package_name)
            logger.info(f"Application {package_name} launched successfully")
            return True
        except Exception as e:
            logger.error(f"Error launching application {package_name}: {e}")
            return False

    @staticmethod
    def stop_app(device: u2.Device, package_name: str) -> bool:
        try:
            device.app_stop(package_name)
            logger.info(f"Application {package_name} stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping application {package_name}: {e}")
            return False

    @staticmethod
    def is_app_installed(device: u2.Device, package_name: str) -> bool:
        try:
            return device.app_info(package_name) is not None
        except Exception as e:
            logger.error(f"Error checking installation of {package_name}: {e}")
            return False
