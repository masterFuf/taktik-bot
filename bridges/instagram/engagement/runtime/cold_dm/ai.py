"""OpenRouter AI message generation for the Instagram Cold DM bridge.

The call goes through the shared provider (`build_ai_service(...).text_completion`, then
`_call_openrouter`), the single point every paid call passes through: it reports the cost as
`ai_spend` on the bridge IPC and retries an upstream rate limit. Until 2026-09-24 this module
built its own request and did neither.
"""

from __future__ import annotations

from bridges.instagram.runtime.ipc import _ipc, logger
from taktik.core.app.ai.factory import build_ai_service
from taktik.core.app.ai.providers.openrouter import MODEL_GENERATION
from taktik.core.app.ai.spend import AI_SPEND_DM


def generate_ai_message(username: str, ai_prompt: str, openrouter_api_key: str, ipc=None) -> str:
    """Generate a personalized DM message for a user via OpenRouter.

    Returns an empty string on any failure, so the caller skips the recipient. `ipc` defaults to
    the bridge's own stdout IPC, which is where `ai_spend` is reported.
    """
    try:
        system_prompt = """Tu es un expert en cold outreach Instagram. Tu génères des messages directs personnalisés, naturels et engageants.

Règles:
- Message court (1-3 phrases max)
- Ton amical et professionnel
- Pas de spam, pas de messages génériques
- Adapte le message au contexte donné
- Ne mentionne jamais que tu es une IA
- Réponds UNIQUEMENT avec le texte du message, rien d'autre"""

        user_prompt = f"""Génère un message de prospection Instagram pour @{username}.

Instructions spécifiques:
{ai_prompt}

Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."""

        # The model is read from the shared constant, never hardcoded here: a slug frozen in
        # a bridge survives the migrations and then dies silently, which already happened
        # once when a retired model stayed here while every other call site had moved.
        result = build_ai_service(api_key=openrouter_api_key, ipc=_ipc if ipc is None else ipc).text_completion(
            system_prompt, user_prompt, temperature=0.8, max_tokens=200,
            model=MODEL_GENERATION, label=f"cold_dm @{username}", kind=AI_SPEND_DM,
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
    logger.info(f"AI generated message for @{username} ({len(message)} chars)")
    return message
