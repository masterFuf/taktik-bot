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

__all__ = [
    "scan_clones",
    "CloneInfo",
    "patch_selectors_for_package",
]
