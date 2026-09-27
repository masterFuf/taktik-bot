"""The Taktik Agent explores the hashtags the model chose for the account, not a generic list.

`_generate_hashtag_pool` asks the text model for hashtags that fit the persona, then read the
answer from a `content` key. `AIService.text_completion` answers under `text` (as every other
reader of the Agent does), so the answer was never read: each session paid for the call and
fell back to the generic marketing list, whatever the account's niche.

The answer goes through the real `AIService`; only the HTTP call to OpenRouter is replaced.
"""

import io
import json
import types
import urllib.request

from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
from taktik.core.app.ai.providers.openrouter import AIService

_FALLBACK_HEAD = "socialmediamarketing"


def _answer_with(content):
    body = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "model": "test/model", "usage": {"prompt_tokens": 10, "completion_tokens": 10}}

    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return lambda *_a, **_k: _Response(json.dumps(body).encode("utf-8"))


def _agent():
    agent = object.__new__(TaktikAgentWorkflow)
    agent._persona_block = "Niche: hair salon\nServices: cuts, colour\nTarget: women 25-45"
    agent._hashtag_pool = []
    agent._ai = types.SimpleNamespace(ai_service=AIService(api_key="test-key"))
    return agent


def test_the_pool_is_the_hashtags_the_model_answered(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _answer_with('["hairsalon", "balayage", "#coiffure"]'))
    agent = _agent()

    agent._generate_hashtag_pool()

    assert agent._hashtag_pool == ["hairsalon", "balayage", "coiffure"]


def test_the_generic_list_is_only_a_fallback_for_an_answer_without_a_list(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _answer_with("no list here"))
    agent = _agent()

    agent._generate_hashtag_pool()

    assert agent._hashtag_pool[0] == _FALLBACK_HEAD
