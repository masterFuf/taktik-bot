"""Which model serves which task — the routing, locked.

Since 2026-09-09 the profile classifier and the post describer are NOT the same model, and the
difference is deliberate: the classifier was benched on 60 real cases (41 µ$ against 590, and its
disagreement sits inside the noise our own model shows against its own stored answers), the
describer was not — and cannot be, since its output is free text fed to the comment writer.

The failure this guards against is silent in every way that matters: no run breaks, no test goes
red, and the only thing that says a task moved to the wrong model is the bill, weeks later.
"""

import json

from taktik.core.app.ai.providers.openrouter import (
    MODEL_ANALYSIS,
    MODEL_CLASSIFICATION,
    MODEL_GENERATION,
    AIService,
)


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _record_models(monkeypatch, answer: str):
    """Capture the model of every outgoing request; answer with `answer` as the content."""
    seen: list = []

    def fake_urlopen(request, *_args, **_kwargs):
        body = json.loads(request.data.decode("utf-8"))
        seen.append(body["model"])
        return _Response(
            {
                "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
                "model": body["model"],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return seen


def _service(monkeypatch, tmp_path):
    """A service whose vision calls carry a real (tiny) image, so nothing short-circuits."""
    from PIL import Image

    shot = tmp_path / "profile.png"
    Image.new("RGB", (40, 80), (30, 30, 30)).save(shot)
    return AIService(api_key="test-key"), str(shot)


def test_the_three_models_are_distinct_and_named(monkeypatch):
    """A collapse back to one constant must be a decision, not an accident."""
    assert MODEL_CLASSIFICATION == "qwen/qwen3.7-flash"
    assert MODEL_ANALYSIS != MODEL_CLASSIFICATION
    assert MODEL_GENERATION != MODEL_CLASSIFICATION


def test_classifying_a_profile_uses_the_classification_model(monkeypatch, tmp_path):
    service, shot = _service(monkeypatch, tmp_path)
    seen = _record_models(monkeypatch, '{"niche_category": "beauty_wellness", "niche": "Makeup & Cosmetics"}')

    service.classify_profile_niche(username="someone", screenshot_path=shot)

    assert seen, "no call was made"
    assert set(seen) == {MODEL_CLASSIFICATION}


def test_analysing_a_post_stays_on_the_analysis_model(monkeypatch, tmp_path):
    """Its output is `post_description`, which the comment writer reads.

    Moving it blind is how a cheaper describer degrades comments through the back door — the one
    place where being wrong is visible to a real person.
    """
    service, shot = _service(monkeypatch, tmp_path)
    seen = _record_models(monkeypatch, '{"description": "a plate of food", "post_language": "en"}')

    service.analyze_post(screenshot_path=shot)

    assert seen, "no call was made"
    assert set(seen) == {MODEL_ANALYSIS}
