"""
License management for TAKTIK Bot.
License verification is handled by Electron's license-service (JWT).
This module stores license config locally and provides backward-compatible access.
"""

from .manager import LicenseManager, license_manager, unified_license_manager

# Backward-compatible alias
UnifiedLicenseManager = LicenseManager

__all__ = [
    'LicenseManager',
    'license_manager',
    'unified_license_manager',
    'UnifiedLicenseManager',
]
