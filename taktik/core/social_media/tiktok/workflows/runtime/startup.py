"""TikTok session start, shared by the desktop bridges and the CLI.

Clean restart, Android permission prompt denied, app language detected, own profile read. It
used to live in the bridges only, so a run started from the CLI skipped all of it.

Events go through an injected notifier shaped like the bridge IPC (`status`, `log`, `send`);
without one they go to the log. The caller brings a connected-or-connectable `TikTokManager`:
this module never opens a device connection of its own.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier


@dataclass
class TikTokStartup:
    """What a started session hands to a workflow."""

    device: Any
    bot_username: Optional[str]
    #: The `TikTokManager` the session was started on, for a workflow that restarts TikTok
    #: itself (the welcome DM's outreach); None when the host does not hand it over.
    manager: Any = None


def _emit(notifier: Any, method: str, *args: Any, **kwargs: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args, **kwargs)


def _wait_for_app_surface(device, timeout: float = 4.0) -> bool:
    """Wait until TikTok has drawn its bottom bar, up to `timeout`. True when it has."""
    from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS

    deadline = time.time() + timeout
    while True:
        for selector in NAVIGATION_SELECTORS.home_tab:
            try:
                if device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


def start_tiktok_session(manager, *, notifier: Any = None, fetch_profile: bool = True) -> Optional[str]:
    """Bring TikTok to a known state on `manager`'s device. Returns the acting username, or None."""
    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()

    logger.info("📱 Connecting to device...")
    _emit(notifier, "status", "connecting", "Connecting to device")

    logger.info("📱 Restarting TikTok (clean state)...")
    _emit(notifier, "status", "launching", "Restarting TikTok app")

    if not manager.restart():
        raise RuntimeError("Failed to restart TikTok app")

    # A probe with a ceiling, not a fixed sleep.
    _wait_for_app_surface(manager.device_manager.device, timeout=4.0)

    # A permission dialog belongs to another package and hides TikTok from every selector.
    # Denied, not granted: an engagement run records and films nothing.
    try:
        from taktik.core.shared.device.permissions import PermissionHandler

        handler = PermissionHandler(manager.device_manager.device, getattr(manager, "device_id", None) or "")
        # Raised with the activity or not at all: a short wait is enough.
        if handler.is_visible(timeout=0.6):
            dismissed = handler.deny(rounds=2)
            logger.warning(f"🔐 Boite de permission Android ecartee ({dismissed})")
            _emit(notifier, "log", "info", "Android permission dialog dismissed before starting")
            time.sleep(1.5)
    except Exception as e:
        logger.warning(f"Permission dialog check failed (non-fatal): {e}")

    # With `fetch_profile` the profile walk ends on the home tab by itself.
    try:
        from taktik.core.social_media.tiktok.actions.atomic.navigation.navigation_actions import NavigationActions

        nav_actions = NavigationActions(manager.device_manager.device)
        nav_actions._press_back()
        time.sleep(0.5)
        if not fetch_profile:
            nav_actions.navigate_to_home()
            time.sleep(1)
            logger.info("✅ Navigated to For You feed")
    except Exception as e:
        logger.warning(f"Could not navigate to Home: {e}")

    try:
        from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

        detected_lang = detect_and_optimize(manager.device_manager.device)
        logger.info(f"🌐 TikTok language detected: {detected_lang.upper()}")
        _emit(notifier, "log", "info", f"App language detected: {detected_lang.upper()}")
    except Exception as e:
        logger.warning(f"Language detection failed (non-fatal): {e}")

    bot_username = None
    if fetch_profile:
        try:
            from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import ProfileActions

            logger.info("📊 Fetching own profile info...")
            _emit(notifier, "status", "fetching_profile", "Fetching your TikTok profile info")

            profile_actions = ProfileActions(manager.device_manager.device)
            profile_info = profile_actions.fetch_own_profile()

            if profile_info:
                bot_username = profile_info.username
                logger.info(f"✅ Bot account: @{profile_info.username} ({profile_info.display_name})")
                logger.info(f"   Followers: {profile_info.followers_count}, Following: {profile_info.following_count}")
                logger.info(f"   Photo: {'oui' if profile_info.profile_pic_base64 else 'non'}")

                _emit(
                    notifier,
                    "send",
                    "bot_profile",
                    profile={
                        "username": profile_info.username,
                        "display_name": profile_info.display_name,
                        "followers_count": profile_info.followers_count,
                        "following_count": profile_info.following_count,
                        "likes_count": profile_info.likes_count,
                        "bio": profile_info.bio,
                        "profile_pic_base64": profile_info.profile_pic_base64,
                    },
                )
                logger.info("📤 Bot profile message sent to frontend")
            else:
                logger.warning("❌ Could not fetch profile info - profile_info is None")
        except Exception as e:
            import traceback

            logger.error(f"❌ Error fetching profile info: {e}")
            logger.error(traceback.format_exc())

    # A block seen anywhere in this run becomes one entry of the account's health history.
    from taktik.core.database.account_health import witness_for
    from taktik.core.shared.diagnostics import run_halt

    run_halt.configurer_temoin(witness_for("tiktok", lambda: bot_username))
    return bot_username


__all__ = ["TikTokStartup", "start_tiktok_session"]
