"""Instagram device boundary.

`DeviceFacade` stays platform-specific because it adds Instagram-aware
interaction behavior. `DeviceManager` is only a compatibility shim that
re-exports the shared Android runtime manager.
"""

from .facade import DeviceFacade
from .manager import DeviceManager

__all__ = ['DeviceFacade', 'DeviceManager']
