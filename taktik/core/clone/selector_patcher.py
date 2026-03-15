"""
Selector Patcher — rewrite package-name references inside selector singletons.

When running on a cloned app (e.g. ``com.instagram.androie`` from NomixCloner),
every XPath that contains the original package name in a ``@resource-id`` must
be updated to match the clone's package name.  This module patches the singleton
dataclass instances **in place** — exactly like the compat version-override
system — so the rest of the bot code needs zero changes.

Example: ``com.instagram.android:id/row_feed_button_like``
       → ``com.instagram.androie:id/row_feed_button_like``

Usage:
    from taktik.core.clone.selector_patcher import patch_selectors_for_package

    count = patch_selectors_for_package("instagram", "com.instagram.androie")
    # → all Instagram selector singletons now reference androie resource-ids
"""

from dataclasses import fields as dc_fields
from typing import Any, Dict, List
from loguru import logger


# Original package names (same as detector.py — single source of truth)
_ORIGINAL_PACKAGES = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
}


def patch_selectors_for_package(platform: str, target_package: str) -> int:
    """
    Rewrite all selector singletons for *platform* so that resource-id
    references use *target_package* instead of the original package name.

    This is a no-op if *target_package* equals the original package.

    Args:
        platform: ``"instagram"`` or ``"tiktok"``.
        target_package: The clone's full package name
                        (e.g. ``com.instagram.android.c1``).

    Returns:
        Number of individual string values patched.
    """
    if platform not in _ORIGINAL_PACKAGES:
        logger.error(f"[ClonePatch] Unknown platform: {platform}")
        return 0

    original = _ORIGINAL_PACKAGES[platform]

    if target_package == original:
        logger.debug(f"[ClonePatch] Package is original ({original}), nothing to patch")
        return 0

    # Import domain maps from compat setup (avoids circular imports)
    from taktik.core.compat.setup import (
        INSTAGRAM_SELECTOR_DOMAINS,
        TIKTOK_SELECTOR_DOMAINS,
    )

    domain_map: Dict[str, Dict[str, Any]] = {
        "instagram": INSTAGRAM_SELECTOR_DOMAINS,
        "tiktok": TIKTOK_SELECTOR_DOMAINS,
    }

    domains = domain_map[platform]
    total_patched = 0

    for domain_name, singleton in domains.items():
        count = _patch_singleton_package(singleton, original, target_package)
        total_patched += count

    logger.info(
        f"[ClonePatch] Patched {total_patched} selector value(s) "
        f"for {platform}: {original} → {target_package}"
    )
    return total_patched


def _patch_singleton_package(singleton: Any, old_pkg: str, new_pkg: str) -> int:
    """
    Walk every field of a dataclass singleton and replace *old_pkg* with
    *new_pkg* in all ``str`` and ``List[str]`` values.

    Returns the number of individual string values that were changed.
    """
    patched = 0

    for f in dc_fields(singleton):
        value = getattr(singleton, f.name)

        if isinstance(value, str):
            if old_pkg in value:
                setattr(singleton, f.name, value.replace(old_pkg, new_pkg))
                patched += 1

        elif isinstance(value, list):
            new_list = []
            changed = False
            for item in value:
                if isinstance(item, str) and old_pkg in item:
                    new_list.append(item.replace(old_pkg, new_pkg))
                    changed = True
                    patched += 1
                else:
                    new_list.append(item)
            if changed:
                setattr(singleton, f.name, new_list)

    return patched
