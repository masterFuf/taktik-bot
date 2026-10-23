"""What the CLI injects into the TikTok handlers, so a terminal run starts like a desktop run.

Same startup sequence (clean restart, permission prompt, language, account) and same AI hooks as
the bridges; the events go to the log instead of stdout. When the payload carries no AI key, the
CLI's own (`ai_key.py`: the environment, the key typed at launch, the saved one). The startup and
the account app connect the run's phone (`CliPhone`) when a launcher calls them, not before.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.cli.hosts.ai_key import ai_block_with_key, require_cli_credential
from taktik.core.ai.credential import AICredential
from taktik.cli.hosts.phone import CliPhone


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def cli_tiktok_startup(phone: CliPhone) -> Callable[..., Any]:
    """Startup provider on the CLI's phone, connected when the launcher starts TikTok; the manager
    reuses that connection."""

    def start():
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.workflows.common.notifier import LoggingWorkflowNotifier
        from taktik.core.social_media.tiktok.workflows.common.startup import (
            TikTokStartup,
            start_tiktok_session,
        )

        device = phone.connect().device
        manager = TikTokManager(phone.device_id)
        # Same reuse as the Lab's app actions: no second connection to the phone.
        manager.device_manager.device = device
        bot_username = start_tiktok_session(manager, notifier=LoggingWorkflowNotifier(), fetch_profile=True)
        return TikTokStartup(device=device, bot_username=bot_username, manager=manager)

    return start


def cli_tiktok_account_app(phone: CliPhone) -> Callable[[Optional[str]], Any]:
    """App provider of the account flows: the app service the account bridge restarts TikTok with,
    on the CLI's phone, connected when the flow asks for it."""

    def app_for(package_name: Optional[str]):
        from taktik.core.shared.device.app_manager import AppService
        from taktik.core.shared.device.connected_device import ConnectedDevice

        connection = ConnectedDevice(phone.connect(), phone.device_id)
        return AppService(connection, platform="tiktok", package_override=package_name)

    return app_for


def cli_tiktok_ai_hooks(ai_config: Mapping[str, Any], language: str) -> None:
    """Install the run's AI hooks, with the CLI's key if the run brings none."""
    ai_config = ai_block_with_key(ai_config)
    if ai_config is None:
        return

    from taktik.core.social_media.tiktok.workflows.common.ai_hooks import install_profile_ai_hooks_for_run

    install_profile_ai_hooks_for_run(ai_config, language, log=_log)


def cli_tiktok_welcome_qualifier(ai_config: Mapping[str, Any], language: str):
    """The new-followers welcome pass's AI verdict, with the CLI's key if the run brings none.
    None when the AI is off."""
    ai_config = ai_block_with_key(ai_config)
    if ai_config is None:
        return None

    from taktik.core.ai.factory import create_ai_service
    from taktik.core.social_media.tiktok.workflows.common.ai_hooks import build_tiktok_profile_qualifier

    enabled, service = create_ai_service(
        ai_config=ai_config, log=_log, ready_message="TikTok AI mode enabled - Profile relevance verdict"
    )
    if not enabled or service is None:
        return None
    return build_tiktok_profile_qualifier(service, ai_config, log=_log, language=language)


def cli_tiktok_outreach_message_generator(ai_prompt: str, credential: AICredential):
    """The cold DM's AI message per recipient, with the CLI's key if the run brings none (or one too short
    to be a key). Without any, the run is refused (`missing_ai_key`): its static messages are not the run
    that asked for the AI."""
    if not credential.usable:
        credential = require_cli_credential()

    from taktik.core.social_media.tiktok.workflows.cold_dm.outreach_message import (
        outreach_message_generator,
    )

    return outreach_message_generator(ai_prompt, credential)


__all__ = [
    "cli_tiktok_account_app",
    "cli_tiktok_ai_hooks",
    "cli_tiktok_outreach_message_generator",
    "cli_tiktok_startup",
    "cli_tiktok_welcome_qualifier",
]
