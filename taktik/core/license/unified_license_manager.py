"""Unified license manager for Taktik Bot."""
import os
import platform
import uuid
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
load_dotenv()


class UnifiedLicenseManager:
    """
    License manager singleton.
    NOTE: License verification is now handled by Electron's license-service (JWT).
    This class only stores license state for backward compatibility.
    The old remote API calls (/auth/verify-license, /usage/*, /api-keys/*) have been removed.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UnifiedLicenseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, api_url: str = None, api_key: str = None):
        if self._initialized:
            return
            
        self.logger = logger.bind(module="unified-license-manager")
        self._api_key = api_key
        self._license_key = None
        self._license_info = None
        self._last_quota_check = None
        self._quota_cache_duration = timedelta(minutes=5)
        self._initialized = True
        
    def _generate_device_fingerprint(self) -> str:
        system_info = {
            'platform': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'node': platform.node(),
            'mac_address': ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                                   for elements in range(0,2*6,2)][::-1])
        }
        
        combined_info = ''.join(str(value) for value in system_info.values())
        return hashlib.sha256(combined_info.encode()).hexdigest()[:32]
    
    def verify_and_setup_license(self, license_key: str) -> Tuple[bool, Optional[str], Optional[dict]]:
        """Legacy method. License verification is now done by Electron via JWT."""
        self.logger.info(f"\ud83d\udd0d License setup: {license_key[:8]}... (stored locally)")
        self._license_key = license_key
        self.save_config(license_key)
        return True, None, {'valid': True, 'message': 'License stored locally'}
    
    def _get_plan_info(self, license_key: str) -> Dict[str, Any]:
        self.logger.debug("ℹ️ Plan info already retrieved via verify-license")
        return {}
    
    def verify_license(self, license_key: str) -> Dict[str, Any]:
        """Legacy method. License verification is now done by Electron via JWT."""
        return {
            'valid': True,
            'message': 'License verified by Electron',
            'device_fingerprint': self._generate_device_fingerprint()
        }
    
    def _get_api_key_from_server(self, license_key: str) -> Optional[str]:
        """Legacy method. API keys are no longer used (JWT only)."""
        return None
    
    # ==================== QUOTA MANAGEMENT ====================
    
    def can_perform_action(self, action_type: str = None) -> bool:
        """Always allow. Quotas are no longer enforced remotely."""
        return True
    
    def get_remaining_actions(self) -> Optional[int]:
        """No longer enforced remotely. Returns unlimited."""
        return 999999
    
    def get_usage_stats(self) -> Optional[Dict[str, Any]]:
        """No longer tracked remotely. Returns defaults."""
        return {
            'actions_used_today': 0,
            'max_actions_per_day': 999999,
            'remaining_actions': 999999
        }
    
    def record_action(self, action_type: str = "general", target: str = None, success: bool = True) -> bool:
        """No-op. Action recording is done locally in SQLite."""
        return True
    
    # ==================== CONFIGURATION ====================
    
    def save_config(self, license_key: str):
        try:
            config_dir = Path.home() / '.taktik'
            config_dir.mkdir(exist_ok=True)
            
            config_file = config_dir / 'license_config.json'
            
            config_data = {
                'license_key': license_key,
                'device_fingerprint': self._generate_device_fingerprint(),
                'last_verification': datetime.now().isoformat(),
                'version': '2.0'
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            os.chmod(config_file, 0o600)
            
            self.logger.info("✅ Configuration saved")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    def load_config(self) -> Optional[Dict[str, Any]]:
        try:
            config_file = Path.home() / '.taktik' / 'license_config.json'
            
            if not config_file.exists():
                return None
            
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            return config_data
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return None
    
    # ==================== UTILITY METHODS ====================
    
    def get_api_key(self) -> Optional[str]:
        return self._api_key
    
    def get_license_key(self) -> Optional[str]:
        return self._license_key
    
    def get_license_info(self) -> Optional[Dict[str, Any]]:
        return self._license_info
    
    def is_configured(self) -> bool:
        return self._api_key is not None and self._license_key is not None
    
    def reset(self):
        self._api_key = None
        self._license_key = None
        self._license_info = None
        self._last_quota_check = None
        self.logger.info("🔄 Configuration reset")


unified_license_manager = UnifiedLicenseManager()
