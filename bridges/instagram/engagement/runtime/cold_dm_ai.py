"""OpenRouter AI message generation for the Instagram Cold DM bridge."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from bridges.instagram.base import logger


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def generate_ai_message(username: str, ai_prompt: str, openrouter_api_key: str) -> str:
    """Generate a personalized DM message for a user via OpenRouter."""
    try:
        system_prompt = """Tu es un expert en cold outreach Instagram. Tu gÃ©nÃ¨res des messages directs personnalisÃ©s, naturels et engageants.

RÃ¨gles:
- Message court (1-3 phrases max)
- Ton amical et professionnel
- Pas de spam, pas de messages gÃ©nÃ©riques
- Adapte le message au contexte donnÃ©
- Ne mentionne jamais que tu es une IA
- RÃ©ponds UNIQUEMENT avec le texte du message, rien d'autre"""

        user_prompt = f"""GÃ©nÃ¨re un message de prospection Instagram pour @{username}.

Instructions spÃ©cifiques:
{ai_prompt}

Le message doit Ãªtre unique et personnalisÃ©. RÃ©ponds uniquement avec le texte du message."""

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://taktik-bot.com",
            "X-Title": "TAKTIK Bot",
        }
        body = json.dumps({
            "model": "anthropic/claude-3.5-haiku",
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
            logger.info(f"AI generated message for @{username}: {message[:50]}...")
            return message
    except Exception as e:
        logger.error(f"AI message generation failed for @{username}: {e}")
        return ""
