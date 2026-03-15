"""
Clone Detector — scan an Android device for cloned app packages.

Supports Instagram and TikTok clones created by NomixCloner, Parallel Space,
Dual Space, etc.  Works by querying `pm list packages` via ADB and matching
against known original package names.

NomixCloner naming convention:
  - Original:  com.instagram.android
  - Clone 1:   com.instagram.androie   (last letter changed: d → e)
  - Clone 2:   com.instagram.androif   (d → f)
  - Clone 3:   com.instagram.androig   (d → g)
  - Or with suffixes: com.instagram.android.c1, .clone2, etc.

To be future-proof, we match any package that starts with a common prefix
(e.g. ``com.instagram.andro``) rather than relying on specific patterns.

Usage:
    from taktik.core.clone import scan_clones

    clones = scan_clones("192.168.1.10:5555", platform="instagram")
    # → [CloneInfo(package="com.instagram.android", is_original=True, ...),
    #    CloneInfo(package="com.instagram.androie", is_original=False, ...)]
"""

import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional
from loguru import logger


# Original package names per platform
ORIGINAL_PACKAGES = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
}

# Prefix-based detection: any package starting with this prefix is a
# potential Instagram/TikTok instance (original or clone).
# NomixCloner mutates the last letter(s): android → androie, androif, …
# Other cloners may append suffixes: android.c1, android.clone2, …
# Using a generous prefix catches both patterns.
_CLONE_PREFIXES = {
    "instagram": "com.instagram.andro",
    "tiktok": "com.zhiliaoapp.musical",
}


@dataclass(frozen=True)
class CloneInfo:
    """Describes a single app instance (original or clone) on a device."""

    package: str
    """Full package name (e.g. ``com.instagram.android.c1``)."""

    is_original: bool
    """True if this is the unmodified, original app."""

    clone_suffix: Optional[str] = None
    """The suffix appended by the cloner (e.g. ``.c1``), None for originals."""

    label: Optional[str] = None
    """Human-readable label (e.g. ``Instagram (clone 1)``)."""

    version: Optional[str] = None
    """Installed version string, populated when ``detect_versions=True``."""


def scan_clones(
    device_id: str,
    platform: str = "instagram",
    adb_command: str = "adb",
    detect_versions: bool = False,
) -> List[CloneInfo]:
    """
    Scan a device for all instances (original + clones) of a given platform.

    Args:
        device_id: ADB device serial (e.g. ``192.168.1.10:5555``).
        platform: ``"instagram"`` or ``"tiktok"``.
        adb_command: Path or alias for the ADB binary.
        detect_versions: If True, run ``dumpsys package`` per clone to get
                         the installed version.  Slower but informative.

    Returns:
        List of :class:`CloneInfo`, original first then clones sorted by name.
    """
    if platform not in ORIGINAL_PACKAGES:
        logger.error(f"[Clone] Unknown platform: {platform}")
        return []

    original_pkg = ORIGINAL_PACKAGES[platform]
    prefix = _CLONE_PREFIXES[platform]

    # Query all installed packages
    try:
        result = subprocess.run(
            [adb_command, "-s", device_id, "shell", "pm", "list", "packages"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.error(f"[Clone] pm list packages failed: {result.stderr.strip()}")
            return []
    except FileNotFoundError:
        logger.error(f"[Clone] ADB command not found: {adb_command}")
        return []
    except subprocess.TimeoutExpired:
        logger.error(f"[Clone] ADB timeout scanning packages on {device_id}")
        return []

    # Parse output: each line is "package:com.example.app"
    all_packages = [
        line.split(":", 1)[1].strip()
        for line in result.stdout.splitlines()
        if line.startswith("package:")
    ]

    # Filter: keep original + anything matching the clone prefix
    matches: List[CloneInfo] = []
    for pkg in sorted(all_packages):
        if not pkg.startswith(prefix):
            continue

        if pkg == original_pkg:
            matches.append(CloneInfo(
                package=pkg,
                is_original=True,
                label=_make_label(platform, None),
            ))
        else:
            # Derive a human-readable diff from the original
            diff = _package_diff(original_pkg, pkg)
            matches.append(CloneInfo(
                package=pkg,
                is_original=False,
                clone_suffix=diff,
                label=_make_label(platform, diff),
            ))

    # Optionally detect versions
    if detect_versions and matches:
        matches = [
            CloneInfo(
                package=c.package,
                is_original=c.is_original,
                clone_suffix=c.clone_suffix,
                label=c.label,
                version=_get_version(device_id, c.package, adb_command),
            )
            for c in matches
        ]

    logger.info(
        f"[Clone] Found {len(matches)} {platform} instance(s) on {device_id}: "
        + ", ".join(c.package for c in matches)
    )
    return matches


def _package_diff(original: str, clone: str) -> str:
    """Return the part of *clone* that differs from *original*.

    Examples:
        _package_diff("com.instagram.android", "com.instagram.androie") → "androie"
        _package_diff("com.instagram.android", "com.instagram.android.c1") → ".c1"
    """
    # Find the longest common prefix
    i = 0
    while i < len(original) and i < len(clone) and original[i] == clone[i]:
        i += 1
    # If divergence is mid-segment, back up to the last dot for readability
    last_dot = clone.rfind(".", 0, i)
    if last_dot > 0 and i < len(original):
        return clone[last_dot + 1:]
    return clone[i:] if i < len(clone) else clone.rsplit(".", 1)[-1]


def _make_label(platform: str, diff: Optional[str]) -> str:
    """Build a human-readable label for display in the UI."""
    name = platform.capitalize()
    if diff is None:
        return name
    clean = diff.lstrip(".")
    # Try to extract a number from common patterns like "c1", "clone2"
    num_match = re.search(r"(\d+)$", clean)
    if num_match:
        return f"{name} (clone {num_match.group(1)})"
    return f"{name} ({clean})"


def _get_version(device_id: str, package: str, adb_command: str) -> Optional[str]:
    """Get the installed version of a package via dumpsys."""
    try:
        result = subprocess.run(
            [adb_command, "-s", device_id, "shell", "dumpsys", "package", package],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("versionName="):
                return line.split("=", 1)[1].strip()
    except Exception as e:
        logger.warning(f"[Clone] Failed to get version for {package}: {e}")
    return None
