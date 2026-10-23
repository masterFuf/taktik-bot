"""The cold DM's AI message: one text per recipient, written from the operator's prompt.

Through the text provider, never the media one: `build_ai_service(...).text_completion` goes
through `_call_model`, which retries an upstream rate limit and reports the cost as `ai_spend` on
the IPC it is given (the bridge hands its stdout; the CLI none). The model is the service's
generation model, the policy's for the key's provider: a slug frozen here would survive the next
migration and then die silently, which already happened once in the bridge this came from.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from loguru import logger

from taktik.core.ai.credential import AICredential

SYSTEM_PROMPT = (
    "Tu es un expert en cold outreach TikTok. Tu génères des messages directs "
    "personnalisés, naturels et engageants.\n\n"
    "Règles:\n"
    "- Message court (1-3 phrases max)\n"
    "- Ton amical et adapté à TikTok\n"
    "- Pas de spam, pas de messages génériques\n"
    "- Adapte le message au contexte donné\n"
    "- Ne mentionne jamais que tu es une IA\n"
    "- Réponds UNIQUEMENT avec le texte du message, rien d'autre"
)


def generate_outreach_message(username: str, ai_prompt: str, credential: AICredential, *, ipc: Any = None) -> str:
    """A personalised cold DM for @username, or "" on any failure (the caller then falls back on
    the static list)."""
    try:
        from taktik.core.ai import factory
        from taktik.core.ai.spend import AI_SPEND_DM

        user_prompt = (
            f"Génère un message de prospection TikTok pour @{username}.\n\n"
            f"Instructions spécifiques:\n{ai_prompt}\n\n"
            "Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."
        )
        service = factory.build_ai_service(api_key=credential.api_key, provider=credential.provider, ipc=ipc)
        result = service.text_completion(
            SYSTEM_PROMPT, user_prompt, temperature=0.8, max_tokens=200,
            model=service.model_generation, label=f"tiktok_dm_outreach @{username}", kind=AI_SPEND_DM,
        )
    except Exception as e:
        logger.error(f"AI message generation failed for @{username}: {e}")
        return ""

    if not result.get("success"):
        logger.error(f"AI message generation failed for @{username}: {result.get('error')}")
        return ""
    message = result.get("text", "")
    if message.startswith('"') and message.endswith('"'):
        message = message[1:-1]
    logger.info(f"AI generated TikTok DM for @{username} ({len(message)} chars)")
    return message


def outreach_message_generator(ai_prompt: str, credential: AICredential, *,
                               ipc: Any = None) -> Optional[Callable[[str], str]]:
    """One message per recipient, or None without a prompt or a key to write with."""
    if not (ai_prompt and credential.usable):
        return None
    return lambda username: generate_outreach_message(username, ai_prompt, credential, ipc=ipc)


__all__ = ["SYSTEM_PROMPT", "generate_outreach_message", "outreach_message_generator"]
