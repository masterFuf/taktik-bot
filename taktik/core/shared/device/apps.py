"""Platform app package/activity catalog for bridge device services."""

from copy import deepcopy
from typing import Dict, List


APPS = {
    "instagram": {
        "package": "com.instagram.android",
        "activity": "com.instagram.mainactivity.InstagramMainActivity",
        "launch_wait": 4,
        "stop_wait": 1,
    },
    "tiktok": {
        "package": "com.zhiliaoapp.musically",
        "activity": "com.ss.android.ugc.aweme.splash.SplashActivity",
        "launch_wait": 4,
        "stop_wait": 1.5,
    },
    "threads": {
        "package": "com.instagram.barcelona",
        "activity": "com.instagram.barcelona.mainactivity.BarcelonaMainActivity",
        "launch_wait": 4,
        "stop_wait": 1,
    },
    "gmail": {
        "package": "com.google.android.gm",
        "activity": "com.google.android.gm.ui.MailActivityGmail",
        "launch_wait": 3,
        "stop_wait": 1,
    },
    "youtube": {
        "package": "com.google.android.youtube",
        "activity": "com.google.android.youtube.app.honeycomb.Shell$HomeActivity",
        "launch_wait": 4,
        "stop_wait": 1,
    },
}


PLATFORM_ALTERNATIVES = {
    "tiktok": [
        "com.zhiliaoapp.musically",
        "com.ss.android.ugc.trill",
        "com.ss.android.ugc.aweme",
    ],
}


def get_app_config(platform: str) -> Dict[str, object] | None:
    """Return a copy of the app config for a platform."""
    config = APPS.get(platform)
    return deepcopy(config) if config else None


def known_platforms() -> List[str]:
    """Return platform keys supported by AppService."""
    return list(APPS.keys())


def packages_for_platform(platform: str) -> List[str]:
    """Return default package plus known alternatives without duplicates."""
    config = APPS.get(platform)
    if not config:
        return []

    packages = [config["package"]]
    for package_name in PLATFORM_ALTERNATIVES.get(platform, []):
        if package_name not in packages:
            packages.append(package_name)
    return packages


def alternatives_for_platform(platform: str) -> List[str]:
    """Return known package alternatives for a platform."""
    return list(PLATFORM_ALTERNATIVES.get(platform, []))
