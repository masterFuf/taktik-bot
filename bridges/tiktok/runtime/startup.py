"""TikTok app startup support for bridge runners."""

import time

from bridges.tiktok.runtime.ipc import logger, send_log, send_message, send_status


def _wait_for_app_surface(device, timeout: float = 4.0) -> bool:
    """Wait until TikTok has drawn something, up to `timeout`. True when it has.

    Cheap on purpose: it asks whether the bottom navigation bar exists, which is the first thing
    every TikTok screen carries, and returns the moment it does. A phone that is genuinely slow
    still gets the whole ceiling.
    """
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


def tiktok_startup(device_id: str, fetch_profile: bool = True):
    """
    Common TikTok startup sequence used by most workflow bridges.

    Returns `(manager, bot_username)`, where `bot_username` is None when profile
    fetching is disabled or unavailable.
    """
    from taktik.core.social_media.tiktok import TikTokManager

    logger.info("📱 Connecting to device...")
    send_status("connecting", "Connecting to device")

    manager = TikTokManager(device_id=device_id)

    logger.info("📱 Restarting TikTok (clean state)...")
    send_status("launching", "Restarting TikTok app")

    if not manager.restart():
        raise RuntimeError("Failed to restart TikTok app")

    # A PROBE, not a blind sleep. TikTok needs a moment to draw its first screen, and this waited
    # a flat four seconds for it -- on every start, whether the app was ready in one second or in
    # four. Measured on a real start: the bottom bar was up well before the sleep ran out.
    # The ceiling stays four seconds, so a slow phone is no worse off than before.
    _wait_for_app_surface(manager.device_manager.device, timeout=4.0)

    # An Android permission dialog sits ON TOP of TikTok and belongs to another package, so
    # every selector below it resolves nothing. Measured on device: a "let TikTok record audio"
    # prompt left a Followers run reporting "Failed to open search" -- a sentence about the
    # search field, on a screen that had none of TikTok on it. The handler already existed and
    # was wired only to the publish and YouTube paths; the engagement workflows never saw it.
    #
    # DENY, not grant: an engagement run records nothing and films nothing, so a permission it
    # never needs must not be granted while nobody is watching.
    try:
        from taktik.core.shared.device.permissions import PermissionHandler

        handler = PermissionHandler(manager.device_manager.device, device_id)
        # 0.6 s, not the 2 s default. An Android permission dialog is raised WITH the activity --
        # it is either there when the app draws or it is not, it does not arrive late. The full
        # timeout was therefore paid in full on every start where there was no dialog, which is
        # every start but the rare one this guard exists for.
        if handler.is_visible(timeout=0.6):
            dismissed = handler.deny(rounds=2)
            logger.warning(f"🔐 Boite de permission Android ecartee ({dismissed})")
            send_log("info", "Android permission dialog dismissed before starting")
            time.sleep(1.5)
    except Exception as e:
        logger.warning(f"Permission dialog check failed (non-fatal): {e}")

    # Going home here is only worth it when nothing else is about to move us. With
    # `fetch_profile` on -- which is every engagement bridge -- the very next thing this function
    # does is walk to the profile and back, so this navigation was the FIRST of three trips to
    # the home tab in one startup. The profile walk ends on the home tab by itself.
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
        send_log("info", f"App language detected: {detected_lang.upper()}")
    except Exception as e:
        logger.warning(f"Language detection failed (non-fatal): {e}")

    bot_username = None
    if fetch_profile:
        try:
            from taktik.core.social_media.tiktok.actions.business.actions.profile_actions import ProfileActions

            logger.info("📊 Fetching own profile info...")
            send_status("fetching_profile", "Fetching your TikTok profile info")

            profile_actions = ProfileActions(manager.device_manager.device)
            profile_info = profile_actions.fetch_own_profile()

            if profile_info:
                bot_username = profile_info.username
                logger.info(f"✅ Bot account: @{profile_info.username} ({profile_info.display_name})")
                logger.info(f"   Followers: {profile_info.followers_count}, Following: {profile_info.following_count}")
                logger.info(f"   Photo: {'oui' if profile_info.profile_pic_base64 else 'non'}")

                # Everything that was read, not a subset of it. Two fields the profile page
                # gives -- the like count and the bio -- were being dropped here for no reason,
                # so a front that wanted them had to go and fetch the profile a second time.
                send_message(
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

    return manager, bot_username
