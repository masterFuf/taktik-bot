"""Business logic for Instagram license management."""

import time
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from ...core.base_action import BaseAction


class LicenseBusiness(BaseAction):
    
    def __init__(self, device, session_manager=None):
        super().__init__(device)
        self.session_manager = session_manager
        self.logger = logger.bind(module="instagram-license-business")
        
        self.action_types = {
            'LIKE': 'like',
            'FOLLOW': 'follow', 
            'UNFOLLOW': 'unfollow',
            'COMMENT': 'comment',
            'STORY_VIEW': 'story_view',
            'STORY_LIKE': 'story_like',
            'VISIT_PROFILE': 'visit_profile'
        }
    
    def can_perform_action(self, action_type: str, api_key: str = None) -> Tuple[bool, str]:
        try:
            from taktik.core.license.manager import unified_license_manager
            
            if not unified_license_manager:
                self.logger.warning("License manager not available")
                return True, "License manager not available"
            
            can_perform = unified_license_manager.can_perform_action(action_type, api_key)
            
            if not can_perform:
                remaining = unified_license_manager.get_remaining_actions(api_key)
                reason = f"Quota exceeded. Remaining actions: {remaining}"
                self.logger.warning(f"Action {action_type} blocked: {reason}")
                return False, reason
            
            return True, "OK"
            
        except Exception as e:
            self.logger.error(f"License check error: {e}")
            return True, f"License check error: {e}"
    
    def record_action(self, action_type: str, username: str = None, 
                     api_key: str = None, metadata: Dict[str, Any] = None) -> bool:
        try:
            from taktik.core.license.manager import unified_license_manager
            
            if not unified_license_manager:
                self.logger.warning("License manager not available for recording")
                return False
            
            success = unified_license_manager.record_usage(
                action_type=action_type,
                api_key=api_key,
                target_username=username,
                metadata=metadata or {}
            )
            
            if success:
                self.logger.debug(f"Action {action_type} recorded for @{username}")
            else:
                self.logger.warning(f"Failed to record action {action_type}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error recording action: {e}")
            return False
    
    def get_license_status(self, api_key: str = None) -> Dict[str, Any]:
        try:
            from taktik.core.license.manager import unified_license_manager
            
            if not unified_license_manager:
                return {
                    'available': False,
                    'error': 'License manager not available'
                }
            
            remaining_actions = unified_license_manager.get_remaining_actions(api_key)
            license_info = unified_license_manager.get_license_info(api_key)
            
            return {
                'available': True,
                'remaining_actions': remaining_actions,
                'license_info': license_info,
                'daily_limit': license_info.get('daily_limit', 0) if license_info else 0,
                'actions_used_today': (license_info.get('daily_limit', 0) - remaining_actions) if license_info else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting license status: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def validate_action_with_license(self, action_type: str, username: str = None,
                                   api_key: str = None) -> Tuple[bool, str]:
        try:
            can_perform, reason = self.can_perform_action(action_type, api_key)
            
            if not can_perform:
                return False, reason
            
            if action_type in ['LIKE', 'FOLLOW', 'UNFOLLOW', 'COMMENT', 'STORY_VIEW', 'STORY_LIKE']:
                self.record_action(action_type, username, api_key)
            
            return True, "Action authorized"
            
        except Exception as e:
            self.logger.error(f"Error validating action: {e}")
            return True, f"Validation error (action allowed): {e}"
    
    def get_daily_usage_summary(self, api_key: str = None) -> Dict[str, Any]:
        try:
            license_status = self.get_license_status(api_key)
            
            if not license_status['available']:
                return license_status
            
            daily_limit = license_status.get('daily_limit', 0)
            remaining = license_status.get('remaining_actions', 0)
            used = daily_limit - remaining
            
            percentage_used = (used / daily_limit * 100) if daily_limit > 0 else 0
            
            return {
                'daily_limit': daily_limit,
                'actions_used': used,
                'actions_remaining': remaining,
                'percentage_used': round(percentage_used, 1),
                'status': 'active' if remaining > 0 else 'quota_exceeded'
            }
            
        except Exception as e:
            self.logger.error(f"Error getting usage summary: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }
    
    def check_quota_warnings(self, api_key: str = None, 
                           warning_thresholds: List[int] = None) -> List[str]:
        if warning_thresholds is None:
            warning_thresholds = [80, 90, 95]
        
        warnings = []
        
        try:
            usage = self.get_daily_usage_summary(api_key)
            
            if usage.get('status') == 'error':
                return [f"Quota check error: {usage.get('error', 'Unknown')}"]
            
            percentage_used = usage.get('percentage_used', 0)
            remaining = usage.get('actions_remaining', 0)
            
            for threshold in sorted(warning_thresholds, reverse=True):
                if percentage_used >= threshold:
                    warnings.append(f"Quota at {percentage_used}% ({remaining} actions remaining)")
                    break
            
            if usage.get('status') == 'quota_exceeded':
                warnings.append("Daily quota exceeded - No additional actions allowed")
            
            return warnings
            
        except Exception as e:
            self.logger.error(f"Error checking warnings: {e}")
            return [f"Error checking warnings: {e}"]
