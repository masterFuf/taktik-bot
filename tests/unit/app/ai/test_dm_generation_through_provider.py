"""The three DM generators reach OpenRouter through the provider, never on their own.

Until 2026-09-24 the Instagram Cold DM, the TikTok DM outreach and the CLI's DM auto-reply each
built their own `urlopen` request. Their cost never reached `ai_spend`, the session's only cost
ledger, and the rate-limit retry added to the provider on 2026-09-10 did not cover them. They now
call `build_ai_service(...).text_completion`, which goes through `_call_openrouter`. Same prompt, same model,
same temperature, same token budget, same 30 s socket timeout.
"""

import asyncio
import io
import json
import pathlib
import urllib.error
import urllib.request

import pytest

from taktik.core.app.ai.providers import openrouter as provider
from taktik.core.app.ai.providers.openrouter import MODEL_GENERATION

REPO = pathlib.Path(__file__).resolve().parents[4]  # tests/unit/app/ai/<file> -> core

# The prompts, to the accent: the first L2 repair of the night was precisely these strings.
COLD_DM_SYSTEM = """Tu es un expert en cold outreach Instagram. Tu génères des messages directs personnalisés, naturels et engageants.

Règles:
- Message court (1-3 phrases max)
- Ton amical et professionnel
- Pas de spam, pas de messages génériques
- Adapte le message au contexte donné
- Ne mentionne jamais que tu es une IA
- Réponds UNIQUEMENT avec le texte du message, rien d'autre"""

COLD_DM_USER = """Génère un message de prospection Instagram pour @lea.

Instructions spécifiques:
Parle de sa boulangerie

Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."""

TIKTOK_SYSTEM = (
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

TIKTOK_USER = (
    "Génère un message de prospection TikTok pour @tom.\n\n"
    "Instructions spécifiques:\nTalk about skate\n\n"
    "Le message doit être unique et personnalisé. Réponds uniquement avec le texte du message."
)


class _RecordingIpc:
    def __init__(self):
        self.spend = []

    def ai_spend(self, cost_usd, model=None, label=None, kind="other"):
        self.spend.append({"cost_usd": cost_usd, "model": model, "label": label, "kind": kind})


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _answer(text, cost=0.00021):
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "model": MODEL_GENERATION,
        "usage": {"prompt_tokens": 120, "completion_tokens": 20, "cost": cost},
    }


@pytest.fixture
def http(monkeypatch):
    """Record every request the provider sends; answer from a queue (a payload or an exception)."""
    calls = []
    answers = []

    def fake_urlopen(request, timeout=None, **_kw):
        calls.append({"url": request.full_url, "body": json.loads(request.data.decode("utf-8")),
                      "timeout": timeout})
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Resp(answer)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(provider.time, "sleep", lambda _s: None)
    return calls, answers


def _rate_limited():
    return urllib.error.HTTPError(provider.OPENROUTER_API_URL, 429, "Too Many Requests", {},
                                  io.BytesIO(b'{"error": "Please retry shortly"}'))


# ---------------------------------------------------------------- Instagram Cold DM


def test_cold_dm_goes_through_the_provider_and_reports_its_cost(http):
    from bridges.instagram.engagement.runtime.cold_dm.ai import generate_ai_message

    calls, answers = http
    answers.append(_answer('"Salut Lea, ton dernier post m\'a fait sourire !"'))
    ipc = _RecordingIpc()

    message = generate_ai_message("lea", "Parle de sa boulangerie", "key", ipc=ipc)

    assert message == "Salut Lea, ton dernier post m'a fait sourire !"
    assert len(calls) == 1
    body = calls[0]["body"]
    assert calls[0]["url"] == provider.OPENROUTER_API_URL
    assert calls[0]["timeout"] == 30
    assert body["model"] == MODEL_GENERATION
    assert body["temperature"] == 0.8
    assert body["max_tokens"] == 200
    assert body["messages"] == [
        {"role": "system", "content": COLD_DM_SYSTEM},
        {"role": "user", "content": COLD_DM_USER},
    ]
    # What the provider adds, on purpose: reasoning off (a reasoning model left on its default
    # spends the whole 200-token budget thinking and answers nothing), and the cost breakdown.
    assert body["reasoning"] == {"enabled": False}
    assert body["usage"] == {"include": True}
    assert ipc.spend == [{"cost_usd": 0.00021, "model": MODEL_GENERATION,
                          "label": "cold_dm @lea", "kind": "dm"}]


def test_cold_dm_retries_a_rate_limit_instead_of_dropping_the_message(http):
    from bridges.instagram.engagement.runtime.cold_dm.ai import generate_ai_message

    calls, answers = http
    answers.extend([_rate_limited(), _answer("Bonjour !")])

    assert generate_ai_message("lea", "x", "key", ipc=_RecordingIpc()) == "Bonjour !"
    assert len(calls) == 2


def test_cold_dm_returns_empty_on_failure_so_the_recipient_is_skipped(http):
    from bridges.instagram.engagement.runtime.cold_dm.ai import generate_ai_message

    _calls, answers = http
    answers.append(urllib.error.HTTPError(provider.OPENROUTER_API_URL, 500, "boom", {},
                                          io.BytesIO(b"server error")))

    assert generate_ai_message("lea", "x", "key", ipc=_RecordingIpc()) == ""


# ---------------------------------------------------------------- TikTok DM outreach


def test_tiktok_outreach_goes_through_the_provider_and_reports_its_cost(http):
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach_message import (
        generate_outreach_message,
    )

    calls, answers = http
    answers.append(_answer('"Hello from TikTok"'))
    ipc = _RecordingIpc()

    assert generate_outreach_message("tom", "Talk about skate", "key", ipc=ipc) == "Hello from TikTok"
    body = calls[0]["body"]
    assert calls[0]["timeout"] == 30
    assert body["model"] == MODEL_GENERATION
    assert body["temperature"] == 0.8
    assert body["max_tokens"] == 200
    assert body["messages"] == [
        {"role": "system", "content": TIKTOK_SYSTEM},
        {"role": "user", "content": TIKTOK_USER},
    ]
    assert ipc.spend[0]["kind"] == "dm"
    assert ipc.spend[0]["label"] == "tiktok_dm_outreach @tom"


def test_tiktok_outreach_returns_empty_on_failure(http):
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach_message import (
        generate_outreach_message,
    )

    _calls, answers = http
    answers.append(RuntimeError("network down"))

    assert generate_outreach_message("tom", "x", "key", ipc=_RecordingIpc()) == ""


# ---------------------------------------------------------------- CLI DM auto-reply


def _auto_reply(ipc=None):
    from taktik.core.social_media.instagram.workflows.management.dm.auto_reply_models import (
        DMAutoReplyConfig,
    )
    from taktik.core.social_media.instagram.workflows.management.dm.llm_integration import (
        DMLLMIntegrationMixin,
    )

    class _Workflow(DMLLMIntegrationMixin):
        def __init__(self):
            import logging
            self.logger = logging.getLogger("test")
            self.conversation_history = {}
            self.ipc = ipc

    # A model distinct from MODEL_GENERATION, so the test sees which one is actually sent.
    config = DMAutoReplyConfig(openrouter_api_key="key", system_prompt="Be nice.",
                               llm_model="test/configured-model")
    return _Workflow(), config


def test_auto_reply_goes_through_the_provider_with_its_configured_model(http):
    calls, answers = http
    answers.append(_answer('Reply: "Merci beaucoup !"'))
    ipc = _RecordingIpc()
    workflow, config = _auto_reply(ipc)

    reply = asyncio.run(workflow._generate_reply_with_llm("Coucou", "ctx", config))

    assert reply == "Merci beaucoup !"
    body = calls[0]["body"]
    assert calls[0]["timeout"] == 30
    assert body["model"] == "test/configured-model"
    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 150
    assert body["messages"] == [
        {"role": "system", "content": "Be nice."},
        {"role": "user", "content": "ctx\n\nUser message: Coucou\n\nYour reply (keep it natural and concise):"},
    ]
    assert ipc.spend[0]["kind"] == "dm"


def test_auto_reply_without_an_ipc_still_answers(http):
    _calls, answers = http
    answers.append(_answer("Ok"))
    workflow, config = _auto_reply(ipc=None)

    assert asyncio.run(workflow._generate_reply_with_llm("Coucou", "ctx", config)) == "Ok"


def test_auto_reply_returns_none_on_failure(http):
    _calls, answers = http
    answers.append(RuntimeError("network down"))
    workflow, config = _auto_reply()

    assert asyncio.run(workflow._generate_reply_with_llm("Coucou", "ctx", config)) is None


# ---------------------------------------------------------------- one door


def test_no_module_calls_openrouter_outside_the_provider():
    """The provider is the only place that builds an OpenRouter request."""
    offenders = []
    for root in ("taktik", "bridges"):
        for path in (REPO / root).rglob("*.py"):
            if path.name == "openrouter.py" and path.parent.name == "providers":
                continue
            text = path.read_text(encoding="utf-8-sig")
            if "openrouter.ai/api" in text or ("urlopen" in text and "OPENROUTER" in text):
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == []
