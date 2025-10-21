from typing import Optional
from loguru import logger
from .....license import unified_license_manager


class LicenseHelpers:
    
    def __init__(self, automation):
        self.automation = automation
        self.logger = logger.bind(module="license-helpers")
        self.license_limits_enabled = False
        
    def get_license_key_from_config(self) -> Optional[str]:
        try:
            config = unified_license_manager.load_config()
            license_key = config.get('license_key') if config else None
            
            if license_key:
                self.logger.debug("✅ License key retrieved from config")
            else:
                self.logger.warning("⚠️ No license key found in config")
                
            return license_key
            
        except Exception as e:
            self.logger.error(f"❌ Error retrieving license key: {e}")
            return None
    
    def initialize_license_limits(self, api_key: Optional[str] = None) -> bool:
        try:
            license_key = self.get_license_key_from_config()
            
            if not license_key:
                self.logger.warning("❌ Cannot initialize license limits - no license key")
                self.license_limits_enabled = False
                return False
            
            verification_result = unified_license_manager.verify_license(license_key)
            
            if verification_result.get('valid'):
                self.logger.info("🔒 License limits initialized successfully (API verification)")
                self.license_limits_enabled = True
                return True
            else:
                reason = verification_result.get('reason', 'Unknown reason')
                self.logger.warning(f"❌ License verification failed: {reason}")
                self.license_limits_enabled = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error initializing license limits: {e}")
            self.license_limits_enabled = False
            return False
    
    def check_action_limits(self, action_type: str, account_username: Optional[str] = None) -> bool:
        if not self.license_limits_enabled:
            self.logger.debug(f"License limits disabled - allowing action {action_type}")
            return True
        
        try:
            license_key = self.get_license_key_from_config()
            if not license_key:
                self.logger.warning("⚠️ No license key - blocking action for safety")
                return False
            
            can_perform = unified_license_manager.can_perform_action(action_type)
            
            if not can_perform:
                self.logger.warning(f"🚫 Action {action_type} blocked: Quota exhausted")
                return False
            
            self.logger.debug(f"✅ Action {action_type} allowed by license")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error checking action limits: {e}")
            return True
    
    def record_action_performed(self, action_type: str, account_username: Optional[str] = None) -> bool:
        if not self.license_limits_enabled:
            self.logger.debug(f"License limits disabled - skipping action recording for {action_type}")
            return True
        
        try:
            license_key = self.get_license_key_from_config()
            if not license_key:
                self.logger.warning("⚠️ No license key - cannot record action")
                return False
            
            unified_license_manager.record_action(action_type)
            self.logger.debug(f"📊 Action {action_type} recorded in license system")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error recording action: {e}")
            return False
