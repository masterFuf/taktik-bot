"""Resolve installed TikTok package variants for standalone workflows."""

from __future__ import annotations

import subprocess
from typing import Callable

from taktik.core.clone.packages.package_map import get_original_package, get_package_variants


DEFAULT_TIKTOK_PACKAGE = get_original_package("tiktok")
KNOWN_TIKTOK_PACKAGES = list(get_package_variants("tiktok"))
RunFn = Callable[..., subprocess.CompletedProcess]


def resolve_tiktok_package(
    device_id: str,
    default: str = DEFAULT_TIKTOK_PACKAGE,
    *,
    run: RunFn = subprocess.run,
) -> str:
    """Return the first known TikTok package installed on the device."""
    for package_name in dict.fromkeys(KNOWN_TIKTOK_PACKAGES):
        try:
            result = run(
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
