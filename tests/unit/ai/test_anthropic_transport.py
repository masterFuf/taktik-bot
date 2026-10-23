"""The Anthropic transport: the same service, the Messages API behind `ModelTransport`.

No network: `urllib.request.urlopen` is replaced by a scripted provider, as in the OpenRouter tests.
What is held here is what differs from OpenRouter and must not drift: the request (key header,
version, no temperature, thinking off, the system blocks, the images), the cost (computed at the
public prices and said to be), the retries, and the refusals that protect a key and the ledger.
"""

import io
import json
import urllib.error
import urllib.request

import pytest
from loguru import logger

from taktik.core.ai.credential import ForeignKeyError
from taktik.core.ai.openrouter_policy import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MODEL,
    ANTHROPIC_PRICES_USD_PER_MTOK,
    ANTHROPIC_THINKING_OFF_FORMS,
    MODEL_GENERATION,
    RATE_LIMIT_BACKOFF_SECONDS,
)
from taktik.core.ai.prompting import cacheable_system
from taktik.core.ai.providers.anthropic import ANTHROPIC_API_URL, anthropic_messages, public_price_cost
from taktik.core.ai.providers.openrouter import AIService

KEY = "sk-ant-api03-" + "k" * 40


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _message(text="une vraie reponse", *, usage=None, model=ANTHROPIC_MODEL, stop_reason="end_turn", **extra):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}] if text is not None else [],
        "stop_reason": stop_reason,
        "usage": usage or {"input_tokens": 1000, "output_tokens": 100},
        **extra,
    }


def _refusal(code, message):
    body = json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": message}})
    return urllib.error.HTTPError(ANTHROPIC_API_URL, code, "err", {}, io.BytesIO(body.encode()))


class _Ipc:
    def __init__(self):
        self.spends = []

    def ai_spend(self, cost, model=None, label=None, kind=None, **beside):
        self.spends.append({"cost": cost, "model": model, "kind": kind, **beside})


@pytest.fixture
def provider(monkeypatch):
    """A scripted Anthropic: every request recorded, answers taken from a queue."""
    sent = []
    answers = []
    waits = []

    def fake_urlopen(request, timeout=None, **_kw):
        sent.append({
            "url": request.full_url,
            "headers": {k.lower(): v for k, v in request.header_items()},
            "body": json.loads(request.data.decode("utf-8")),
        })
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Response(answer)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: waits.append(seconds))
    return sent, answers, waits


def _service(ipc=None):
    return AIService(api_key=KEY, ipc=ipc, provider="anthropic")


# ------------------------------------------------------------------------------- the request


def test_a_text_call_goes_to_the_messages_api_with_the_key_and_no_temperature(provider):
    sent, answers, _ = provider
    answers.append(_message("Bonjour"))

    result = _service().text_completion("Tu es un assistant.", "Dis bonjour", temperature=0.9, max_tokens=50)

    assert result["success"] is True and result["text"] == "Bonjour"
    assert result["provider"] == "anthropic"
    request = sent[0]
    assert request["url"] == ANTHROPIC_API_URL
    assert request["headers"]["x-api-key"] == KEY
    assert request["headers"]["anthropic-version"] == ANTHROPIC_API_VERSION
    body = request["body"]
    assert body["model"] == ANTHROPIC_MODEL
    assert body["max_tokens"] == 50
    assert "temperature" not in body
    assert body["thinking"] == {"type": "disabled"}
    assert body["system"] == [{"type": "text", "text": "Tu es un assistant."}]
    assert body["messages"] == [{"role": "user", "content": "Dis bonjour"}]


def test_every_task_runs_on_the_anthropic_model_of_the_policy(provider):
    service = _service()

    assert service.model_generation == service.model_classification == service.model_analysis == ANTHROPIC_MODEL
    assert service.model_generation != MODEL_GENERATION


def test_an_image_becomes_a_base64_block_and_the_cached_prefix_passes_unchanged(provider, tmp_path):
    sent, answers, _ = provider
    answers.append(_message('{"ok": true}'))
    image = tmp_path / "shot.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    system = cacheable_system("stable part", "variable part")

    result = _service().vision_completion(system, "Decris", str(image))

    assert result["success"] is True
    body = sent[0]["body"]
    assert body["system"] == system  # cache_control is Anthropic's own format
    image_block, text_block = body["messages"][0]["content"]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"].startswith("image/")
    assert image_block["source"]["data"] and not image_block["source"]["data"].startswith("data:")
    assert text_block == {"type": "text", "text": "Decris"}


def test_the_translation_keeps_strings_and_web_images():
    system, turns = anthropic_messages([
        {"role": "system", "content": "regle"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://x.test/a.png"}},
                                     {"type": "text", "text": "et ca ?"}]},
    ])

    assert system == [{"type": "text", "text": "regle"}]
    assert turns[0]["content"][0] == {"type": "image", "source": {"type": "url", "url": "https://x.test/a.png"}}


# ------------------------------------------------------------------------------- the cost


def test_the_cost_is_computed_at_the_public_prices_and_said_to_be(provider):
    sent, answers, _ = provider
    usage = {"input_tokens": 2000, "output_tokens": 300,
             "cache_creation_input_tokens": 1500, "cache_read_input_tokens": 4000}
    answers.append(_message("ok", usage=usage))
    ipc = _Ipc()
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="INFO")
    try:
        result = _service(ipc).text_completion("s", "u", label="t", kind="comment")
    finally:
        logger.remove(sink)

    price = ANTHROPIC_PRICES_USD_PER_MTOK[ANTHROPIC_MODEL]
    expected = (2000 * price["input"] + 1500 * price["cache_write"] + 4000 * price["cache_read"]
                + 300 * price["output"]) / 1_000_000
    assert result["cost_usd"] == pytest.approx(expected)
    assert result["cost_basis"] == "public_price"
    assert ipc.spends == [{"cost": pytest.approx(expected), "model": ANTHROPIC_MODEL, "kind": "comment",
                           "provider": "anthropic", "cost_basis": "public_price"}]
    assert any("(public price)" in line and "tokens=7500 (cached 4000)+300" in line for line in lines)


def test_a_prompt_over_the_threshold_pays_the_long_prices_for_the_whole_request():
    short = public_price_cost("claude-haiku-5-5", {"input_tokens": 100_000, "output_tokens": 1000})
    long = public_price_cost("claude-haiku-5-5", {"input_tokens": 90_000, "cache_read_input_tokens": 10_001,
                                                  "output_tokens": 1000})

    assert short == pytest.approx((100_000 * 0.10 + 1000 * 0.50) / 1_000_000)
    assert long == pytest.approx((90_000 * 0.50 + 10_001 * 0.05 + 1000 * 2.50) / 1_000_000)


def test_every_model_the_policy_sends_to_anthropic_has_a_price():
    from taktik.core.ai.openrouter_policy import MODELS_BY_TASK, PROVIDER_ANTHROPIC

    for task, models in MODELS_BY_TASK.items():
        assert models[PROVIDER_ANTHROPIC] in ANTHROPIC_PRICES_USD_PER_MTOK, task


def test_a_model_without_a_price_is_never_called(provider):
    sent, answers, _ = provider

    result = _service()._call_model("claude-unknown-9", [{"role": "user", "content": "hi"}])

    assert result["success"] is False
    assert "no public price" in result["error"]
    assert sent == []


def test_a_billed_empty_answer_and_a_refusal_still_reach_the_ledger(provider):
    _, answers, _ = provider
    answers.append(_message(None, usage={"input_tokens": 500, "output_tokens": 0}))
    answers.append(_message("", usage={"input_tokens": 500, "output_tokens": 3}, stop_reason="refusal",
                            stop_details={"type": "refusal", "category": "cyber"}))
    ipc = _Ipc()
    service = _service(ipc)

    empty = service.text_completion("s", "u")
    refused = service.text_completion("s", "u")

    assert empty["success"] is False and "empty answer" in empty["error"]
    assert refused["success"] is False and "refused" in refused["error"]
    assert [spend["provider"] for spend in ipc.spends] == ["anthropic", "anthropic"]


# ------------------------------------------------------------------------------- retries and refusals


def test_thinking_off_falls_back_form_by_form_and_is_remembered(provider):
    sent, answers, _ = provider
    answers.extend([
        _refusal(400, "thinking.type: disabled is not supported for this model"),
        _refusal(400, "thinking.type: between_tools is not supported for this model"),
        _message("ok"),
        _message("ok again"),
    ])
    service = _service()

    first = service._call_model("claude-opus-5-5", [{"role": "user", "content": "hi"}])
    second = service._call_model("claude-opus-5-5", [{"role": "user", "content": "hi"}])

    assert first["success"] and second["success"]
    shapes = [{k: request["body"][k] for k in ("thinking", "output_config") if k in request["body"]}
              for request in sent]
    assert shapes == [dict(form) for form in ANTHROPIC_THINKING_OFF_FORMS] + [dict(ANTHROPIC_THINKING_OFF_FORMS[2])]


def test_overloaded_is_retried_with_the_policy_waits_and_a_bad_request_is_not(provider):
    sent, answers, waits = provider
    answers.extend([_refusal(529, "Overloaded"), _message("ok")])
    assert _service()._call_model(ANTHROPIC_MODEL, [{"role": "user", "content": "hi"}])["success"] is True
    assert waits == [RATE_LIMIT_BACKOFF_SECONDS[0]]

    sent.clear()
    waits.clear()
    answers.extend([_refusal(400, "credit balance is too low"), _message("never read")])
    result = _service()._call_model(ANTHROPIC_MODEL, [{"role": "user", "content": "hi"}])
    assert result["success"] is False and result["rate_limited"] is False
    assert len(sent) == 1 and waits == []


def test_a_key_is_never_sent_to_the_other_provider(provider):
    sent, _, _ = provider

    with pytest.raises(ForeignKeyError):
        AIService(api_key=KEY, provider="openrouter")
    with pytest.raises(ForeignKeyError):
        AIService(api_key="sk-or-v1-" + "o" * 40, provider="anthropic")
    with pytest.raises(ValueError):
        AIService(api_key=KEY, provider="mistral")
    assert sent == []


def test_the_spend_line_spells_the_providers_and_the_cost_bases_as_the_engine_does():
    from taktik.core.ai.openrouter_policy import AI_PROVIDERS
    from taktik.core.ai.providers.transport import COST_BILLED, COST_PUBLIC_PRICE
    from taktik.core.contract.shared import AI_SPEND_COST_BASES, AI_SPEND_PROVIDERS

    assert AI_SPEND_PROVIDERS == AI_PROVIDERS
    assert AI_SPEND_COST_BASES == (COST_BILLED, COST_PUBLIC_PRICE)
