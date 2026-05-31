"""Clone package metadata owners."""

ORIGINAL_PACKAGES = {
    "instagram": "com.instagram.android",
    "tiktok": "com.zhiliaoapp.musically",
}

CLONE_PREFIXES = {
    "instagram": "com.instagram.andro",
    "tiktok": "com.zhiliaoapp.musical",
}

OFFICIAL_PACKAGE = ORIGINAL_PACKAGES["instagram"]


def get_original_package(platform: str) -> str:
    """Return the official package name for a supported platform."""
    return ORIGINAL_PACKAGES[platform]


def get_clone_prefix(platform: str) -> str:
    """Return the clone detection prefix for a supported platform."""
    return CLONE_PREFIXES[platform]
