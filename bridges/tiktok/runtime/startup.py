"""TikTok app startup support for bridge runners."""

import time

from bridges.tiktok.runtime.ipc import logger, send_log, send_message, send_status


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

    time.sleep(4)

    try:
        from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions

        nav_actions = NavigationActions(manager.device_manager.device)
        nav_actions._press_back()
        time.sleep(0.5)
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

                send_message(
                    "bot_profile",
                    profile={
                        "username": profile_info.username,
                        "display_name": profile_info.display_name,
                        "followers_count": profile_info.followers_count,
                        "following_count": profile_info.following_count,
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
