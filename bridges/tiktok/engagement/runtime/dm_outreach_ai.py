"""OpenRouter AI message generation for the TikTok DM outreach bridge.

Message generation goes through the text provider, never the media one. Mirrors the
Instagram cold-DM path
(`bridges/instagram/engagement/runtime/cold_dm/ai.py`): the call goes through the shared
provider (`build_ai_service(...).text_completion`, then `_call_openrouter`), which reports
the cost as `ai_spend` on the bridge IPC and retries an upstream rate limit.
"""

from __future__ import annotations

from bridges.tiktok.runtime.ipc import _ipc, logger
from taktik.core.app.ai.factory import build_ai_service
from taktik.core.app.ai.providers.openrouter import MODEL_GENERATION
from taktik.core.app.ai.spend import AI_SPEND_DM


def generate_ai_message(username: str, ai_prompt: str, openrouter_api_key: str, ipc=None) -> str:
    """Generate a personalized TikTok DM message for a user via OpenRouter.

    Returns an empty string on any failure so the caller can fall back to the
    static message list. `ipc` defaults to the bridge's own stdout IPC, which is where
    `ai_spend` is reported.
    """
    try:
        system_prompt = (
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

        user_prompt = (
            f"Génère un message de prospection TikTok pour @{username}.\n\n"
            f"Instructions spécifiques:\n{ai_prompt}\n\n"
            "Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."
        )

        # The model is read from the shared constant, never hardcoded here: a slug frozen in
        # a bridge survives the migrations and then dies silently, which already happened
        # once when a retired model stayed here while every other call site had moved.
        result = build_ai_service(api_key=openrouter_api_key, ipc=_ipc if ipc is None else ipc).text_completion(
            system_prompt, user_prompt, temperature=0.8, max_tokens=200,
            model=MODEL_GENERATION, label=f"tiktok_dm_outreach @{username}", kind=AI_SPEND_DM,
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


__all__ = ["generate_ai_message"]
