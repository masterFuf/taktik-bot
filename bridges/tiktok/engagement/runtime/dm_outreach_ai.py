"""OpenRouter AI message generation for the TikTok DM outreach bridge.

Message generation goes through the text provider, never the media one. Mirrors the
Instagram cold-DM path
(`bridges/instagram/engagement/runtime/cold_dm/ai.py`).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from bridges.tiktok.runtime.ipc import logger
from taktik.core.app.ai.providers.openrouter import MODEL_GENERATION


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def generate_ai_message(username: str, ai_prompt: str, openrouter_api_key: str) -> str:
    """Generate a personalized TikTok DM message for a user via OpenRouter.

    Returns an empty string on any failure so the caller can fall back to the
    static message list.
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

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://taktik-bot.com",
            "X-Title": "TAKTIK Bot",
        }
        body = json.dumps({
            # The model is read from the shared constant, never hardcoded here: a slug frozen in
            # a bridge survives the migrations and then dies silently, which already happened
            # once when a retired model stayed here while every other call site had moved.
            "model": MODEL_GENERATION,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 200,
        }).encode("utf-8")

        req = urllib.request.Request(OPENROUTER_API_URL, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {}).get("content", "").strip()
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]
            logger.info(f"AI generated TikTok DM for @{username} ({len(message)} chars)")
            return message
    except Exception as e:
        logger.error(f"AI message generation failed for @{username}: {e}")
        return ""


__all__ = ["generate_ai_message"]
