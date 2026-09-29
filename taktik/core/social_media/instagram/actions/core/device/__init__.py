"""Instagram device boundary.

`DeviceFacade` stays platform-specific because it adds Instagram-aware
interaction behavior. `DeviceManager` is only a compatibility shim that
re-exports the shared Android runtime manager.
"""

from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.core.device.manager import DeviceManager

__all__ = ['DeviceFacade', 'DeviceManager']
