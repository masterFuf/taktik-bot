"""
Clone Support — detect and manage cloned app instances (NomixCloner, etc.).

Two main entry points:
  - scan_clones()              → detect all Instagram/TikTok clones on a device
  - patch_selectors_for_package() → rewrite resource-id references in selector
                                    singletons so XPath matches the clone's
                                    package name instead of the original.
"""

from .detector import scan_clones, CloneInfo
from .selector_patcher import patch_selectors_for_package

# ── Global active-package registry ──────────────────────────────────
# Set once by DesktopBridge before running a workflow so that any code
# (deep-link navigation, app management, etc.) can resolve the correct
# package without needing a direct reference to the automation object.
_active_package: str = "com.instagram.android"


def set_active_package(pkg: str) -> None:
    """Set the active Instagram package (original or clone)."""
    global _active_package
    _active_package = pkg


def get_active_package() -> str:
    """Return the active Instagram package."""
    return _active_package


__all__ = [
    "scan_clones",
    "CloneInfo",
    "patch_selectors_for_package",
    "set_active_package",
    "get_active_package",
]
