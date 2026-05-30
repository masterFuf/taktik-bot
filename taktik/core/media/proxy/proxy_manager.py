"""Compatibility shim for Instagram media proxy management."""

from taktik.core.social_media.instagram.media.proxy.proxy_manager import (
    ProxyManager,
    resolve_media_scripts_dir,
)

__all__ = ["ProxyManager", "resolve_media_scripts_dir"]
