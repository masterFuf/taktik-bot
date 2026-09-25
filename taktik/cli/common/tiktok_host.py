"""What the CLI injects into the TikTok handlers, so a terminal run starts like a desktop run.

Same startup sequence (clean restart, permission prompt, language, account) and same AI hooks as
the bridges; the events go to the log instead of stdout. The AI key comes from
`OPENROUTER_API_KEY` when the payload does not carry one.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Mapping, Optional

from loguru import logger

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"


def _log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def cli_tiktok_startup(device: Any, device_id: str) -> Callable[..., Any]:
    """Startup provider on the CLI's connected device; the manager reuses that connection."""

    def start():
        from taktik.core.social_media.tiktok import TikTokManager
        from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier
        from taktik.core.social_media.tiktok.workflows.runtime.startup import (
            TikTokStartup,
            start_tiktok_session,
        )

        manager = TikTokManager(device_id)
        # Same reuse as the Lab's app actions: no second connection to the phone.
        manager.device_manager.device = device
        bot_username = start_tiktok_session(manager, notifier=LoggingWorkflowNotifier(), fetch_profile=True)
        return TikTokStartup(device=device, bot_username=bot_username, manager=manager)

    return start


def _with_key(ai_config: Mapping[str, Any]) -> Optional[dict]:
    """The run's `ai` block with a key, from the environment if the run brings none; None when AI
    is off or no key is available."""
    ai_config = dict(ai_config or {})
    if not ai_config.get("enabled"):
        return None

    if not ai_config.get("openrouterApiKey"):
        key = os.environ.get(OPENROUTER_KEY_ENV, "").strip()
        if not key:
            logger.warning(
                f"AI requested but {OPENROUTER_KEY_ENV} is not set: this run goes on without AI"
            )
            return None
        ai_config["openrouterApiKey"] = key
    return ai_config


def cli_tiktok_ai_hooks(ai_config: Mapping[str, Any], language: str) -> None:
    """Install the run's AI hooks, with the key from the environment if the run brings none."""
    ai_config = _with_key(ai_config)
    if ai_config is None:
        return

    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import install_profile_ai_hooks_for_run

    install_profile_ai_hooks_for_run(ai_config, language, log=_log)


def cli_tiktok_welcome_qualifier(ai_config: Mapping[str, Any], language: str):
    """The new-followers welcome pass's AI verdict, with the key from the environment if the run
    brings none. None when no AI service can be built."""
    ai_config = _with_key(ai_config)
    if ai_config is None:
        return None

    from taktik.core.app.ai.factory import create_ai_service
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import build_tiktok_profile_qualifier

    enabled, service = create_ai_service(
        ai_config=ai_config, log=_log, ready_message="TikTok AI mode enabled - Profile relevance verdict"
    )
    if not enabled or service is None:
        return None
    return build_tiktok_profile_qualifier(service, ai_config, log=_log, language=language)


__all__ = ["OPENROUTER_KEY_ENV", "cli_tiktok_ai_hooks", "cli_tiktok_startup", "cli_tiktok_welcome_qualifier"]
