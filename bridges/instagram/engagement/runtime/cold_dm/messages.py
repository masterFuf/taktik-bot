"""Message selection helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import random

from bridges.instagram.engagement.runtime.cold_dm.ai import generate_ai_message
from bridges.instagram.runtime.ipc import logger


def choose_cold_dm_message(
    *,
    recipient: str,
    messages: list,
    use_ai: bool,
    ai_prompt: str,
    openrouter_api_key: str,
) -> str | None:
    if use_ai:
        message = generate_ai_message(recipient, ai_prompt, openrouter_api_key)
        if not message:
            logger.warning(f"AI generation failed for @{recipient}, skipping")
        return message

    return random.choice(messages)
