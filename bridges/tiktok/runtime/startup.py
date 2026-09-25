"""TikTok app startup for bridge runners.

The sequence itself lives in the core (`taktik.core.social_media.tiktok.workflows.runtime.startup`)
so the CLI runs the same one; the bridge builds the manager and prints the events on stdout.
"""

from bridges.tiktok.runtime.ipc import _ipc


def tiktok_startup(device_id: str, fetch_profile: bool = True):
    """
    Common TikTok startup sequence used by most workflow bridges.

    Returns `(manager, bot_username)`, where `bot_username` is None when profile
    fetching is disabled or unavailable.
    """
    from taktik.core.social_media.tiktok import TikTokManager
    from taktik.core.social_media.tiktok.workflows.runtime.startup import start_tiktok_session

    manager = TikTokManager(device_id=device_id)
    bot_username = start_tiktok_session(manager, notifier=_ipc, fetch_profile=fetch_profile)
    return manager, bot_username


__all__ = ["tiktok_startup"]
