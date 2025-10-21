import subprocess
from typing import List, Dict, Optional
import uiautomator2 as u2
from loguru import logger


class DeviceManager:
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.device = None
    
    @classmethod
    def list_devices(cls) -> List[Dict[str, str]]:
        try:
            result = subprocess.run(
                ["adb", "devices"], 
                capture_output=True, 
                text=True,
                check=True
            )
            
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    device_id, status = line.strip().split('\t')
                    devices.append({"id": device_id, "status": status})
            
            return devices
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error listing devices: {e}")
            return []
    
    def connect(self, device_id: Optional[str] = None) -> bool:
        try:
            if device_id:
                self.device_id = device_id
            
            if not self.device_id:
                devices = self.list_devices()
                if not devices:
                    logger.error("No device connected")
                    return False
                self.device_id = devices[0]["id"]
            
            self.device = u2.connect(self.device_id)
            logger.info(f"Connected to device: {self.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to device {self.device_id}: {e}")
            return False
    
    def is_app_installed(self, package_name: str) -> bool:
        if not self.device:
            if not self.connect():
                return False
                
        try:
            return self.device.app_info(package_name) is not None
        except Exception as e:
            logger.error(f"Error checking if {package_name} is installed: {e}")
            return False
    
    def launch_app(self, package_name: str, activity: Optional[str] = None) -> bool:
        if not self.device:
            if not self.connect():
                return False
                
        try:
            if activity:
                self.device.app_start(package_name, activity, stop=True)
            else:
                self.device.app_start(package_name, stop=True)
            
            logger.info(f"Application {package_name} launched successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch application {package_name}: {e}")
            return False
    
    def stop_app(self, package_name: str) -> bool:
        if not self.device:
            if not self.connect():
                return False
                
        try:
            self.device.app_stop(package_name)
            logger.info(f"Application {package_name} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop application {package_name}: {e}")
            return False
