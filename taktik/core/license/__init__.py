from .unified_license_manager import UnifiedLicenseManager, unified_license_manager
from .quota_exceeded_exception import QuotaExceededException
from .quota_handler import display_quota_exceeded_message

LicenseManager = UnifiedLicenseManager
license_manager = unified_license_manager
get_license_manager = lambda: unified_license_manager
api_license_manager = unified_license_manager
api_key_manager = unified_license_manager
SimpleLimitsManager = UnifiedLicenseManager
APILicenseManager = UnifiedLicenseManager
APIKeyManager = UnifiedLicenseManager

__all__ = [
    'UnifiedLicenseManager', 'unified_license_manager',
    'LicenseManager', 'license_manager', 'get_license_manager',
    'api_license_manager', 'api_key_manager', 
    'SimpleLimitsManager', 'APILicenseManager', 'APIKeyManager',
    'QuotaExceededException', 'display_quota_exceeded_message'
]
