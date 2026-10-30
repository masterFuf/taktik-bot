"""TikTok app startup for bridge runners.

The sequence itself lives in the core (`taktik.core.social_media.tiktok.workflows.common.startup`)
so the CLI runs the same one; the bridge builds the manager and prints the events on stdout.
"""

import sys

from bridges.common.network import send_run_refusal
from bridges.tiktok.common.ipc import _ipc
from taktik.core.shared.diagnostics.run_halt import RunRefused


def tiktok_startup(device_id: str, fetch_profile: bool = True):
    """
    Common TikTok startup sequence used by most workflow bridges.

    Returns `(manager, bot_username)`, where `bot_username` is None when profile
    fetching is disabled or unavailable.

    A phone the session start's network door refuses ends the process here, exit 1, on its
    `NETWORK_UNREACHABLE` line: the workflow bridges report any other failure of their run as an
    uncoded `Workflow error`, which would come after it and hide the motive from the desktop.
    """
    from taktik.core.social_media.tiktok import TikTokManager
    from taktik.core.social_media.tiktok.workflows.common.startup import start_tiktok_session

    manager = TikTokManager(device_id=device_id)
    try:
        bot_username = start_tiktok_session(manager, notifier=_ipc, fetch_profile=fetch_profile)
    except RunRefused as refused:
        send_run_refusal(refused, "Workflow")
        sys.exit(1)
    return manager, bot_username


def tiktok_startup_provider(device_id: str):
    """The startup a core launcher takes (`tiktok_startup`): this sequence, events on stdout, the
    manager handed over with the device and the account."""

    def start():
        from taktik.core.social_media.tiktok.workflows.common.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username, manager=manager)

    return start


__all__ = ["tiktok_startup", "tiktok_startup_provider"]
