"""Resolve installed TikTok package variants for standalone workflows."""

from __future__ import annotations

import subprocess

from taktik.core.social_media.tiktok.core.manager import TIKTOK_PACKAGES


DEFAULT_TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
KNOWN_TIKTOK_PACKAGES = [*TIKTOK_PACKAGES, "com.bytedance.trill"]


def resolve_tiktok_package(device_id: str, default: str = DEFAULT_TIKTOK_PACKAGE) -> str:
    """Return the first known TikTok package installed on the device."""
    for package_name in dict.fromkeys(KNOWN_TIKTOK_PACKAGES):
        try:
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "pm", "list", "packages", package_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if package_name in result.stdout:
                return package_name
        except Exception:
            continue

    return default
