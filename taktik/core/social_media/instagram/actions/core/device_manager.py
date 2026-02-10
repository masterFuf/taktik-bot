import subprocess
import time
from typing import List, Dict, Optional, Tuple
import uiautomator2 as u2
from loguru import logger


class DeviceManager:
    # ATX agent packages
    ATX_PACKAGES = [
        "com.github.uiautomator",
        "com.github.uiautomator.test"
    ]
    
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.device = None
        self._atx_verified = False
    
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
    
    def connect(self, device_id: Optional[str] = None, verify_atx: bool = True) -> bool:
        """Connect to device via uiautomator2.
        
        Args:
            device_id: Optional device ID to connect to
            verify_atx: If True, verify ATX agent is working and repair if needed
        """
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
            
            # Verify ATX agent is working (only once per session)
            # Non-blocking: log warning but don't prevent connection
            # The workflow can still work even if ATX is temporarily unhealthy
            if verify_atx and not self._atx_verified:
                if self._verify_and_repair_atx():
                    self._atx_verified = True
                else:
                    logger.warning("⚠️ ATX agent verification failed - continuing anyway (workflow may still work)")
                    # Don't return False: let the workflow attempt to proceed
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to device {self.device_id}: {e}")
            return False
    
    def _verify_and_repair_atx(self, max_retries: int = 2) -> bool:
        """Verify ATX agent is working, attempt repair if not.
        
        Returns:
            True if ATX is working, False if repair failed
        """
        for attempt in range(max_retries + 1):
            is_healthy, error = self._check_atx_health()
            if is_healthy:
                if attempt > 0:
                    logger.info(f"✅ ATX agent repaired successfully after {attempt} attempt(s)")
                else:
                    logger.debug("✅ ATX agent is healthy")
                return True
            
            if attempt < max_retries:
                logger.warning(f"⚠️ ATX agent unhealthy: {error}. Attempting repair ({attempt + 1}/{max_retries})...")
                self._repair_atx()
                time.sleep(2)  # Wait for ATX to initialize
            else:
                logger.error(f"❌ ATX agent repair failed after {max_retries} attempts: {error}")
        
        return False
    
    def _check_atx_health(self) -> Tuple[bool, Optional[str]]:
        """Check if ATX agent is responding properly.
        
        Returns:
            Tuple of (is_healthy, error_message)
        """
        if not self.device:
            return False, "Device not connected"
        
        try:
            # Try a simple operation that requires ATX
            info = self.device.info
            if info and 'displayWidth' in info:
                return True, None
            return False, "Device info incomplete"
        except Exception as e:
            error_msg = str(e)
            # Common ATX errors
            if "uiautomator" in error_msg.lower():
                return False, f"ATX server error: {error_msg}"
            if "timeout" in error_msg.lower():
                return False, f"ATX timeout: {error_msg}"
            if "connection" in error_msg.lower():
                return False, f"ATX connection error: {error_msg}"
            return False, f"ATX check failed: {error_msg}"
    
    def _repair_atx(self) -> bool:
        """Attempt to repair/reinstall ATX agent."""
        logger.info("🔧 Attempting to repair ATX agent...")
        
        try:
            # Method 1: Try to reinitialize via uiautomator2
            if self.device:
                try:
                    # This will reinstall ATX if needed
                    self.device.reset_uiautomator()
                    logger.info("ATX reset via uiautomator2")
                    return True
                except Exception as e:
                    logger.warning(f"reset_uiautomator failed: {e}")
            
            # Method 2: Force reinstall via u2.connect with init=True
            try:
                self.device = u2.connect(self.device_id)
                # Try to force init
                if hasattr(self.device, 'uiautomator'):
                    self.device.uiautomator.start()
                logger.info("ATX restarted via uiautomator.start()")
                return True
            except Exception as e:
                logger.warning(f"uiautomator.start() failed: {e}")
            
            # Method 3: Use ADB to restart ATX service
            try:
                device_arg = ["-s", self.device_id] if self.device_id else []
                # Kill existing uiautomator processes
                subprocess.run(
                    ["adb"] + device_arg + ["shell", "pkill", "-f", "uiautomator"],
                    capture_output=True, timeout=5
                )
                time.sleep(1)
                logger.info("Killed existing uiautomator processes")
                
                # Reconnect to trigger ATX restart
                self.device = u2.connect(self.device_id)
                return True
            except Exception as e:
                logger.warning(f"ADB ATX restart failed: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"ATX repair failed: {e}")
            return False
    
    def get_atx_status(self) -> Dict[str, any]:
        """Get detailed ATX agent status for diagnostics.
        
        Returns:
            Dict with ATX status information
        """
        status = {
            "device_id": self.device_id,
            "connected": self.device is not None,
            "atx_verified": self._atx_verified,
            "atx_healthy": False,
            "atx_packages_installed": [],
            "error": None
        }
        
        # Check ATX packages via ADB
        for pkg in self.ATX_PACKAGES:
            if self._is_app_installed_adb(pkg):
                status["atx_packages_installed"].append(pkg)
        
        # Check ATX health
        if self.device:
            is_healthy, error = self._check_atx_health()
            status["atx_healthy"] = is_healthy
            status["error"] = error
        
        return status
    
    def is_app_installed(self, package_name: str) -> bool:
        """Check if an app is installed using uiautomator2, with ADB fallback."""
        # First try uiautomator2
        if self.device or self.connect():
            try:
                result = self.device.app_info(package_name)
                if result is not None:
                    return True
            except Exception as e:
                logger.warning(f"uiautomator2 check failed for {package_name}: {e}, trying ADB fallback")
        
        # Fallback to ADB direct check (more reliable)
        return self._is_app_installed_adb(package_name)
    
    def _is_app_installed_adb(self, package_name: str) -> bool:
        """Check if an app is installed using ADB directly (fallback method)."""
        try:
            device_arg = ["-s", self.device_id] if self.device_id else []
            result = subprocess.run(
                ["adb"] + device_arg + ["shell", "pm", "list", "packages", package_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            installed = package_name in result.stdout
            if installed:
                logger.info(f"ADB fallback: {package_name} is installed")
            return installed
        except Exception as e:
            logger.error(f"ADB fallback check failed for {package_name}: {e}")
            return False
    
    def launch_app(self, package_name: str, activity: Optional[str] = None, stop_first: bool = False) -> bool:
        if not self.device:
            if not self.connect():
                return False
                
        try:
            if activity:
                self.device.app_start(package_name, activity, stop=stop_first)
            else:
                self.device.app_start(package_name, stop=stop_first)
            
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
