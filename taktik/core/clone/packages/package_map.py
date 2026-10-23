"""Clone package metadata owners."""

from typing import Optional

ORIGINAL_PACKAGES = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
}

PACKAGE_VARIANTS = {
    "instagram": [ORIGINAL_PACKAGES["instagram"]],
    "tiktok": [
        ORIGINAL_PACKAGES["tiktok"],
        "com.ss.android.ugc.trill",
        "com.ss.android.ugc.aweme",
        "com.bytedance.trill",
    ],
}

# A clone made by changing the last letters of the official package (`com.instagram.androie`), or by
# the Cloner of TAKTIK, which gives each clone a package of its own (`com.taktik.ig1`, `com.taktik.tt2`).
CLONE_PREFIXES = {
    "instagram": ("com.instagram.andro", "com.taktik.ig"),
    "tiktok": ("com.zhiliaoapp.musical", "com.taktik.tt"),
}

OFFICIAL_PACKAGE = ORIGINAL_PACKAGES["instagram"]


def get_original_package(platform: str) -> str:
    """Return the official package name for a supported platform."""
    return ORIGINAL_PACKAGES[platform]


def get_package_variants(platform: str) -> tuple[str, ...]:
    """Return known installable package names for a supported platform."""
    return tuple(PACKAGE_VARIANTS[platform])


def get_clone_prefixes(platform: str) -> tuple[str, ...]:
    """Return the package prefixes that detect a clone of a supported platform."""
    return CLONE_PREFIXES[platform]


def belongs_to_platform(package: Optional[str], platform: str) -> bool:
    """Is this package one of `platform`'s apps -- official build, variant, or Taktik clone?

    The single answer to "am I still in the right app". Asking it against ONE constant is the
    mistake this replaces: `com.zhiliaoapp.musically` is only one of four shipping TikTok packages,
    and every Taktik clone carries a suffixed package that matches none of them. A check that says
    "you left the app" while the phone sits in a clone is worse than no check at all -- it would
    stop healthy runs.

    Both halves come from the tables above, so a new variant or a new clone prefix is declared in
    exactly one place. Unknown platform or empty package -> False, and the CALLER decides what that
    means: an unreadable foreground is not a foreign app (see `foreground_package`).
    """
    if not package or platform not in PACKAGE_VARIANTS:
        return False
    if package in PACKAGE_VARIANTS[platform]:
        return True
    return package.startswith(CLONE_PREFIXES[platform])
