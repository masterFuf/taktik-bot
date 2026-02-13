"""
Device Manager (compatibility shim)

Canonical location: taktik.core.shared.device_manager
This file re-exports for backward compatibility.
All existing imports from this path continue to work.
"""

from taktik.core.shared.device.manager import DeviceManager

__all__ = ['DeviceManager']
