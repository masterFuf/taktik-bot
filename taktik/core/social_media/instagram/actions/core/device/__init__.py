"""Device abstraction — Instagram-specific facade and manager shim."""

from .facade import DeviceFacade
from .manager import DeviceManager

__all__ = ['DeviceFacade', 'DeviceManager']
