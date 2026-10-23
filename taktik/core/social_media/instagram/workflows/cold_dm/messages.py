"""Message selection helpers for the Instagram Cold DM workflow."""

from __future__ import annotations

import random

from taktik.core.ai.credential import AICredential
from taktik.core.social_media.instagram.workflows.cold_dm.ai import generate_ai_message
from loguru import logger


def choose_cold_dm_message(
    *,
    recipient: str,
    messages: list,
    use_ai: bool,
    ai_prompt: str,
    ai_credential: AICredential | None,
    ipc=None,
) -> str | None:
    if use_ai and ai_credential is not None:
        message = generate_ai_message(recipient, ai_prompt, ai_credential, ipc=ipc)
        if not message:
            logger.warning(f"AI generation failed for @{recipient}, skipping")
        return message

    return random.choice(messages)
