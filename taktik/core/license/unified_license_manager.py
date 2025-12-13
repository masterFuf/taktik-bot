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
from ..database.api_client import TaktikAPIClient

load_dotenv()


class UnifiedLicenseManager:
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UnifiedLicenseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, api_url: str = None, api_key: str = None):
        if self._initialized:
            return
            
        self.api_client = TaktikAPIClient(api_url, api_key, config_mode=True)
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
        try:
            self.logger.info(f"🔍 Verifying license: {license_key[:8]}...")
            
            validation_result = self.verify_license(license_key)
            if not validation_result.get('valid', False):
                return False, None, validation_result
            
            api_key = self._get_api_key_from_server(license_key)
            if not api_key:
                self.logger.error("❌ Unable to retrieve API key")
                return False, None, validation_result
            
            self.save_config(license_key)
            
            self._license_key = license_key
            self._api_key = api_key
            self._license_info = validation_result
            
            self.api_client = TaktikAPIClient(None, api_key, config_mode=False)
            
            self.logger.success(f"✅ License configured successfully")
            return True, api_key, validation_result
            
        except Exception as e:
            self.logger.error(f"❌ Error configuring license: {e}")
            return False, None, {'valid': False, 'message': str(e)}
    
    def _get_plan_info(self, license_key: str) -> Dict[str, Any]:
        self.logger.debug("ℹ️ Plan info already retrieved via verify-license")
        return {}
    
    def verify_license(self, license_key: str) -> Dict[str, Any]:
        try:
            device_fingerprint = self._generate_device_fingerprint()
            
            response = self.api_client.verify_license(license_key)
            
            if response and response.get('valid', False):
                self.logger.info("✅ Valid license")
                return {
                    'valid': True,
                    'message': 'Valid license',
                    'license_info': response.get('license_info', {}),
                    'plan_info': response.get('plan_info', {}),
                    'device_fingerprint': device_fingerprint
                }
            else:
                message = response.get('message', 'Invalid license') if response else 'Verification error'
                self.logger.warning(f"❌ {message}")
                return {
                    'valid': False,
                    'message': message,
                    'license_info': None
                }
                
        except Exception as e:
            self.logger.error(f"Error verifying license: {e}")
            return {
                'valid': False,
                'message': f'Verification error: {str(e)}',
                'license_info': None
            }
    
    def _get_api_key_from_server(self, license_key: str) -> Optional[str]:
        try:
            response = self.api_client._make_request('GET', f'/api-keys/{license_key}')
            if response and 'api_key' in response:
                api_key = response['api_key']
                self.logger.info(f"✅ API key retrieved: {api_key[:8]}...{api_key[-8:]}")
                return api_key
            else:
                self.logger.error("❌ API key not found in response")
                return None
        except Exception as e:
            self.logger.error(f"❌ Error retrieving API key: {e}")
            return None
    
    # ==================== QUOTA MANAGEMENT ====================
    
    def can_perform_action(self, action_type: str = None) -> bool:
        try:
            remaining_actions = self.get_remaining_actions()
            
            if remaining_actions is None:
                self.logger.error("❌ Unable to check quotas")
                return False
            
            if remaining_actions <= 0:
                self.logger.warning("⚠️ Action quota exhausted")
                return False
            
            self.logger.debug(f"✅ Remaining actions: {remaining_actions}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking quota: {e}")
            return False
    
    def get_remaining_actions(self) -> Optional[int]:
        try:
            if not self._api_key:
                self.logger.error("❌ API key not configured")
                return None
            
            if (self._last_quota_check and 
                datetime.now() - self._last_quota_check < self._quota_cache_duration):
                return getattr(self, '_cached_remaining_actions', None)
            
            response = self.api_client._make_request('GET', f'/usage/remaining-actions-by-api-key')
            
            if response and 'remaining_actions' in response:
                remaining_actions = response['remaining_actions']
                
                self._cached_remaining_actions = remaining_actions
                self._last_quota_check = datetime.now()
                
                return remaining_actions
            else:
                self.logger.error("❌ Invalid response for remaining actions")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving remaining actions: {e}")
            return None
    
    def get_usage_stats(self) -> Optional[Dict[str, Any]]:
        try:
            if not self._api_key:
                self.logger.error("❌ API key not configured")
                return None
            
            response = self.api_client._make_request('GET', f'/usage/remaining-actions-by-api-key')
            
            if response and 'actions_used_today' in response:
                return {
                    'actions_used_today': response['actions_used_today'],
                    'max_actions_per_day': response.get('max_actions_per_day', 5000),
                    'remaining_actions': response.get('remaining_actions', 0)
                }
            else:
                self.logger.debug("ℹ️ Using default statistics")
                return {
                    'actions_used_today': 0,
                    'max_actions_per_day': 5000,
                    'remaining_actions': 5000
                }
                
        except Exception as e:
            self.logger.debug(f"Using default statistics: {e}")
            return {
                'actions_used_today': 0,
                'max_actions_per_day': 5000,
                'remaining_actions': 5000
            }
    
    def record_action(self, action_type: str = "general", target: str = None, success: bool = True) -> bool:
        try:
            if not self._api_key:
                self.logger.error("❌ API key not configured")
                return False
            
            data = {'action_type': action_type}
            if target:
                data['target'] = target
            if not success:
                data['success'] = success
            
            result = self.api_client._make_request('POST', '/usage/record-action', data)
            
            self._last_quota_check = None
            
            return result.get('success', False) if result else False
            
        except Exception as e:
            self.logger.error(f"Error recording action: {e}")
            return False
    
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
