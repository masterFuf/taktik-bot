"""A task with a declared fallback survives its model no longer responding; no other task moves.

The classification runs on a model with one backend. Nothing moved between models before this: a
model retired or down lost every profile of a run. These tests drive the real transport with a fake
network, one scripted answer per model, and read what goes out, what the caller gets and what reaches
the cost ledger.
"""

import io
import json
import threading
import urllib.error

import pytest
from loguru import logger

from taktik.core.ai import openrouter_policy as policy
from taktik.core.ai.providers import openrouter
from taktik.core.ai.providers.openrouter import AIService

PRIMARY = policy.MODEL_CLASSIFICATION
FALLBACK = policy.MODEL_CLASSIFICATION_FALLBACK
CLASSIFICATION = '{"niche_category": "beauty_wellness", "niche": "Makeup & Cosmetics", "summary": ""}'


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _served(model, text=CLASSIFICATION, cost=0.0002):
    return _Response({
        "model": model,
        "provider": "Backend",
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": cost},
    })


def _refusal(status, body="upstream error"):
    return urllib.error.HTTPError(openrouter.OPENROUTER_API_URL, status, "err", {}, io.BytesIO(body.encode()))


class _Network:
    """What each model answers, in order; the last answer of a model repeats. Records each request."""

    def __init__(self, monkeypatch, answers):
        self.answers = {model: list(steps) for model, steps in answers.items()}
        self.requests = []
        self.waits = []
        monkeypatch.setattr("urllib.request.urlopen", self._urlopen)
        monkeypatch.setattr(openrouter.time, "sleep", self.waits.append)

    def _urlopen(self, request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        self.requests.append(body)
        steps = self.answers[body["model"]]
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        step = step(body) if callable(step) else step
        if isinstance(step, Exception):
            raise step
        return step

    @property
    def models(self):
        return [request["model"] for request in self.requests]


class _Ledger:
    """The IPC of a run, as far as the cost and the cards go."""

    def __init__(self):
        self.spend = []
        self.cards = []
        self.errors = []

    def ai_spend(self, cost, model=None, label=None, kind=None, **beside):
        self.spend.append({"cost": cost, "model": model, "kind": kind})

    def ai_profile_analyzing(self, *_args, **_kwargs):
        pass

    def ai_profile_analyzed(self, **fields):
        self.cards.append(fields)

    def ai_error(self, message, _username=None):
        self.errors.append(message)


@pytest.fixture
def warnings():
    captured = []
    handler = logger.add(lambda message: captured.append(str(message)), level="WARNING")
    yield captured
    logger.remove(handler)


@pytest.fixture
def shot(tmp_path):
    from PIL import Image

    path = tmp_path / "profile.png"
    Image.new("RGB", (40, 80), (30, 30, 30)).save(path)
    return str(path)


def _classify(ledger, shot):
    return AIService(api_key="test-key", ipc=ledger).classify_profile_niche(username="someone", screenshot_path=shot)


# ------------------------------------------------------------------- what moves the call


@pytest.mark.parametrize("status", [502, 503, 429])
def test_a_model_still_failing_after_its_retries_moves_to_the_fallback(monkeypatch, shot, status, warnings):
    network = _Network(monkeypatch, {PRIMARY: [_refusal(status)] * 3, FALLBACK: [_served(FALLBACK)]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    # Its retries first: a burst must not change who classifies.
    assert network.models == [PRIMARY, PRIMARY, PRIMARY, FALLBACK]
    assert network.waits == list(policy.RATE_LIMIT_BACKOFF_SECONDS)
    assert result["success"] is True
    assert result["model"] == FALLBACK
    assert any(PRIMARY in line and FALLBACK in line and "falling back" in line for line in warnings)


def test_a_burst_that_clears_stays_on_the_model(monkeypatch, shot):
    network = _Network(monkeypatch, {PRIMARY: [_refusal(429), _served(PRIMARY)], FALLBACK: [_served(FALLBACK)]})

    result = _classify(_Ledger(), shot)

    assert network.models == [PRIMARY, PRIMARY]
    assert result["model"] == PRIMARY


@pytest.mark.parametrize("refusal", [
    _refusal(404, '{"error":{"message":"No endpoints found for particle-ai/particle-1."}}'),
    _refusal(400, '{"error":{"message":"particle-ai/particle-1 is not a valid model ID"}}'),
])
def test_a_retired_model_moves_at_once(monkeypatch, shot, refusal):
    network = _Network(monkeypatch, {PRIMARY: [refusal], FALLBACK: [_served(FALLBACK)]})

    result = _classify(_Ledger(), shot)

    assert network.models == [PRIMARY, FALLBACK]
    assert network.waits == []
    assert result["model"] == FALLBACK


def test_no_answer_at_all_moves_to_the_fallback(monkeypatch, shot):
    network = _Network(monkeypatch, {PRIMARY: [urllib.error.URLError("timed out")], FALLBACK: [_served(FALLBACK)]})

    result = _classify(_Ledger(), shot)

    assert network.models == [PRIMARY, FALLBACK]
    assert result["model"] == FALLBACK


def test_a_model_past_its_total_deadline_moves_and_the_fallback_has_its_own(monkeypatch):
    release = threading.Event()

    def stalled(_body):
        release.wait(10)
        return _served(PRIMARY)

    monkeypatch.setattr("taktik.core.ai.providers.openrouter.MODEL_TOTAL_TIMEOUT_SECONDS", 0.2)
    network = _Network(monkeypatch, {PRIMARY: [stalled], FALLBACK: [_served(FALLBACK, "ok")]})

    result = AIService(api_key="test-key")._call_model(PRIMARY, [], label="t", fallback_model=FALLBACK)
    release.set()

    assert network.models == [PRIMARY, FALLBACK]
    assert result["success"] is True
    assert result["model"] == FALLBACK


def test_a_body_that_carries_the_failure_under_a_200_moves_and_says_it(monkeypatch):
    failed = _Response({"error": {"code": 502, "message": "every provider failed"}})
    network = _Network(monkeypatch, {PRIMARY: [failed], FALLBACK: [_served(FALLBACK, "ok")]})

    service = AIService(api_key="test-key")
    assert "every provider failed" in service._call_model(PRIMARY, [], label="t")["error"]
    network.requests.clear()

    assert service._call_model(PRIMARY, [], label="t", fallback_model=FALLBACK)["model"] == FALLBACK


# -------------------------------------------------------------- what never moves the call


@pytest.mark.parametrize("refusal", [
    _refusal(401, "No auth credentials found"),
    _refusal(402, "Insufficient credits"),
    _refusal(403, "Flagged by moderation"),
    _refusal(400, "messages: invalid image"),
])
def test_a_refusal_that_is_not_the_model_stays_one_call(monkeypatch, shot, refusal):
    """The key or the credits would fail the same on the fallback, and the user must read them."""
    network = _Network(monkeypatch, {PRIMARY: [refusal], FALLBACK: [_served(FALLBACK)]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert network.models == [PRIMARY]
    assert result["success"] is False
    assert ledger.errors


def test_an_answer_that_is_not_json_is_not_a_model_that_did_not_respond(monkeypatch, shot):
    """The model responded: its retry is the one of the JSON call, on the same model."""
    network = _Network(monkeypatch, {PRIMARY: [_served(PRIMARY, "not json")], FALLBACK: [_served(FALLBACK)]})

    _classify(_Ledger(), shot)

    assert network.models == [PRIMARY, PRIMARY]


def test_no_other_task_ever_moves(monkeypatch, shot):
    """Generation writes to real people, the analysis feeds it: neither changes author on a failure."""
    generation = policy.MODEL_GENERATION
    analysis = policy.MODEL_ANALYSIS
    network = _Network(monkeypatch, {
        generation: [_refusal(404)],
        analysis: [_refusal(404)],
        PRIMARY: [_refusal(404)],
        FALLBACK: [_served(FALLBACK)],
    })
    service = AIService(api_key="test-key")

    service.generate_smart_comment(post_description="a plate", username="someone", niche="food")
    service.analyze_post(screenshot_path=shot)
    service.text_completion("s", "u", model=service.model_generation)
    service.vision_completion("s", "u", shot, model=service.model_classification)
    service.classify_following_usernames_batch(["someone"])

    assert FALLBACK not in network.models
    assert {generation, analysis} <= set(network.models)


def test_a_provider_with_no_declared_fallback_stays_on_its_model():
    service = AIService(api_key="sk-ant-test-key", provider=policy.PROVIDER_ANTHROPIC)

    assert service.fallback_classification is None


# ------------------------------------------------------------------- what the caller reads


def test_the_cost_and_the_model_column_are_the_served_model(monkeypatch, shot):
    _Network(monkeypatch, {PRIMARY: [_refusal(404)], FALLBACK: [_served(FALLBACK, cost=0.00015)]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert ledger.spend == [{"cost": 0.00015, "model": FALLBACK, "kind": "profile"}]
    assert ledger.cards[0]["model"] == FALLBACK
    assert ledger.cards[0]["cost_usd"] == 0.00015
    assert result["model"] == FALLBACK
    assert result["cost_usd"] == 0.00015


def test_the_ledger_names_the_model_the_provider_says_it_served(monkeypatch, shot):
    """Not the slug that was asked for: the provider's word is the one the bill is under."""
    dated = f"{FALLBACK}-20260922"
    _Network(monkeypatch, {PRIMARY: [_refusal(404)], FALLBACK: [_served(dated)]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert [line["model"] for line in ledger.spend] == [dated]
    assert result["model"] == dated


def test_a_billed_empty_answer_is_counted_on_its_model_then_the_fallback_on_its_own(monkeypatch, shot):
    _Network(monkeypatch, {
        PRIMARY: [_served(PRIMARY, text="", cost=0.0001)],
        FALLBACK: [_served(FALLBACK, cost=0.00015)],
    })
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert [(line["model"], line["cost"]) for line in ledger.spend] == [(PRIMARY, 0.0001), (FALLBACK, 0.00015)]
    assert result["model"] == FALLBACK


def test_when_both_fail_the_error_names_both(monkeypatch, shot):
    _Network(monkeypatch, {PRIMARY: [_refusal(404, "gone")], FALLBACK: [_refusal(404, "also gone")]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert result["success"] is False
    for said in (PRIMARY, "gone", FALLBACK, "also gone"):
        assert said in result["error"]
    assert ledger.errors == [result["error"]]


def test_each_model_gets_the_reasoning_form_it_accepts(monkeypatch, shot):
    """The primary's form says nothing of the fallback's: learned and remembered per model."""
    network = _Network(monkeypatch, {
        PRIMARY: [_refusal(404)],
        FALLBACK: [_refusal(400, "Reasoning is mandatory for this endpoint"), _served(FALLBACK)],
    })

    result = _classify(_Ledger(), shot)

    assert result["model"] == FALLBACK
    assert [r["reasoning"] for r in network.requests] == [
        policy.REASONING_OFF, policy.REASONING_OFF, policy.REASONING_MINIMAL,
    ]


def test_a_partial_extraction_keeps_who_wrote_it_and_what_it_cost(monkeypatch, shot):
    """An answer cut in the middle still carries a niche: its row must name the model that served it."""
    cut = '{"niche_category": "travel", "niche": "Adventure'
    _Network(monkeypatch, {PRIMARY: [_refusal(404)], FALLBACK: [_served(FALLBACK, cut, cost=0.0001)]})
    ledger = _Ledger()

    result = _classify(ledger, shot)

    assert result["success"] is True
    assert result["classification"]["niche_category"] == "travel"
    assert result["model"] == FALLBACK
    assert result["provider"] == policy.PROVIDER_OPENROUTER
    assert result["cost_usd"] == 0.0001
    assert ledger.cards[0]["model"] == FALLBACK
