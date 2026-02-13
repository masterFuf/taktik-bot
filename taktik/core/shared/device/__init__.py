"""Shared device — facade (UI wrapper) and manager (ADB connection/ATX)."""

from .facade import BaseDeviceFacade, Direction
from .manager import DeviceManager

__all__ = ['BaseDeviceFacade', 'Direction', 'DeviceManager']
