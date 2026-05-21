"""
Clone Support — detect and manage cloned app instances (NomixCloner, etc.).

Public API:
  - scan_clones()                 → detect all Instagram/TikTok clones on a device
  - patch_selectors_for_package() → rewrite resource-id references in selector
                                    dataclasses so XPath matches the clone's
                                    package name instead of the original.
  - CloneAwareDeviceProxy         → transparent device wrapper that rewrites
                                    resourceId / xpath at call time (covers
                                    every selector site reached via the proxy).
  - rid() / rewrite_selector()    → string helper for code that does NOT go
                                    through the device proxy (CLI, recorder,
                                    raw XPath strings, etc.).
  - set_active_package() / get_active_package() → global registry of the
                                    currently-active clone package.
"""

from typing import Optional

from .detector import scan_clones, CloneInfo
from .selector_patcher import patch_selectors_for_package
from .proxy import CloneAwareDeviceProxy, rewrite_selector, OFFICIAL_PACKAGE

# ── Global active-package registry ──────────────────────────────────
# Set once by InstagramBridgeBase._after_connect() before running a workflow
# so that any code (deep-link navigation, app management, rid() helper, …)
# can resolve the correct package without needing a direct reference to the
# automation object.
_active_package: str = OFFICIAL_PACKAGE


def set_active_package(pkg: str) -> None:
    """Set the active Instagram package (original or clone)."""
    global _active_package
    _active_package = pkg


def get_active_package() -> str:
    """Return the active Instagram package."""
    return _active_package


def rid(resource_id: str, *, target_package: Optional[str] = None) -> str:
    """Resolve a resource-id (or string containing the official package) for
    the active clone package.

    Thin convenience wrapper around :func:`rewrite_selector` that defaults
    *target_package* to the globally active package. Safe to call from any
    context — returns the input unchanged when running on stock Instagram.

    Usage::

        from taktik.core.clone import rid
        device(resourceId=rid("com.instagram.android:id/search_tab")).click()
    """
    return rewrite_selector(
        resource_id,
        target_package=target_package if target_package is not None else _active_package,
    )


__all__ = [
    "scan_clones",
    "CloneInfo",
    "patch_selectors_for_package",
    "set_active_package",
    "get_active_package",
    "CloneAwareDeviceProxy",
    "rewrite_selector",
    "rid",
    "OFFICIAL_PACKAGE",
]
