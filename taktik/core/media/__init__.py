"""Media capture module for Instagram images via mitmproxy."""
from .proxy_manager import ProxyManager
from .media_capture import MediaCaptureService

__all__ = ['ProxyManager', 'MediaCaptureService']
