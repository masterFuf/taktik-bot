"""A reasoning model bills in full and can answer nothing at all.

Measured on `qwen/qwen3.7-flash` while benchmarking it as a cheaper replacement for the
profile classifier: left on its default it put 900 tokens into `message.reasoning`, returned
`message.content = null`, stopped on `finish_reason=length`, and cost seven times the same
call with reasoning off. Three separate defects showed up at once, and each is locked here.
"""

import io
import json

from taktik.core.app.ai.providers.openrouter import AIService


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _capture_request(monkeypatch):
    """Answer every call with a usable payload, and hand back the request that was sent."""
    sent = {}

    def fake_urlopen(request, *_args, **_kwargs):
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(
            {
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
                "model": "test/model",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return sent


def test_reasoning_is_disabled_on_every_call(monkeypatch):
    """We ask for JSON, never for a train of thought — and nothing downstream reads one."""
    sent = _capture_request(monkeypatch)

    AIService(api_key="test-key")._call_openrouter(
        "test/model", [{"role": "user", "content": "hello"}]
    )

    assert sent["body"]["reasoning"] == {"enabled": False}


def test_an_endpoint_that_requires_reasoning_is_retried_with_minimal_effort(monkeypatch):
    """No single value switches reasoning off everywhere.

    `qwen3.7-flash` accepts `{"enabled": false}` and ignores `{"effort": "minimal"}`;
    `gpt-5-nano` and `glm-5.3-flash` do the exact opposite and answer HTTP 400 "Reasoning is
    mandatory for this endpoint". Asking for the strong form first and falling back once on
    that message is what covers both — measured on all four models on 2026-09-09.
    """
    import urllib.error

    sent = []

    def fake_urlopen(request, *_args, **_kwargs):
        body = json.loads(request.data.decode("utf-8"))
        sent.append(body["reasoning"])
        if body["reasoning"] == {"enabled": False}:
            raise urllib.error.HTTPError(
                url="https://openrouter.ai",
                code=400,
                msg="Bad Request",
                hdrs=None,
                fp=io.BytesIO(
                    json.dumps(
                        {"error": {"message": "Reasoning is mandatory for this endpoint "
                                              "and cannot be disabled."}}
                    ).encode("utf-8")
                ),
            )
        return _Response(
            {
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
                "model": "test/model",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = AIService(api_key="test-key")._call_openrouter(
        "test/model", [{"role": "user", "content": "hello"}]
    )

    assert result["success"] is True
    assert sent == [{"enabled": False}, {"effort": "minimal"}]


def test_a_quota_error_is_not_retried(monkeypatch):
    """The fallback keys on the reasoning message, not on the status code.

    A blanket retry on 400 would re-send every malformed or quota-refused request, and pay
    for it twice on the endpoints that bill before validating.
    """
    import urllib.error

    calls = []

    def fake_urlopen(request, *_args, **_kwargs):
        calls.append(1)
        raise urllib.error.HTTPError(
            url="https://openrouter.ai", code=400, msg="Bad Request", hdrs=None,
            fp=io.BytesIO(json.dumps({"error": {"message": "Insufficient credits."}}).encode()),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = AIService(api_key="test-key")._call_openrouter(
        "test/model", [{"role": "user", "content": "hello"}]
    )

    assert result["success"] is False
    assert len(calls) == 1


def test_null_content_is_a_failure_not_an_empty_success(monkeypatch):
    """`content` can be present AND null.

    `.get("content", "")` hands back the None rather than the default, and the caller died on
    `.strip()` with "'NoneType' object has no attribute 'strip'" — an error naming a Python
    type instead of the empty answer behind it.
    """

    def fake_urlopen(*_args, **_kwargs):
        return _Response(
            {
                "choices": [{"message": {"content": None, "reasoning": "..."}, "finish_reason": "length"}],
                "usage": {
                    "prompt_tokens": 320,
                    "completion_tokens": 901,
                    "completion_tokens_details": {"reasoning_tokens": 900},
                    "cost": 0.00012673,
                },
                "model": "test/model",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = AIService(api_key="test-key")._call_openrouter(
        "test/model", [{"role": "user", "content": "hello"}]
    )

    assert result["success"] is False
    assert "empty answer" in result["error"]


def test_a_billed_call_that_answered_nothing_still_reaches_the_ledger(monkeypatch):
    """Spend is reported on "were we charged", not on "did it work".

    Gating the ledger on success is how a paid call escapes accounting — the exact defect the
    ai_spend transport was introduced to close. An empty answer costs the same as a good one.
    """

    def fake_urlopen(*_args, **_kwargs):
        return _Response(
            {
                "choices": [{"message": {"content": None}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 320, "completion_tokens": 901, "cost": 0.00012673},
                "model": "test/model",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    spent = []

    class _Ipc:
        def ai_spend(self, cost, model=None, label=None, kind=None):
            spent.append((cost, model, kind))

    service = AIService(api_key="test-key")
    service.ipc = _Ipc()
    result = service._call_openrouter("test/model", [{"role": "user", "content": "hello"}])

    assert result["success"] is False
    assert spent and spent[0][0] == 0.00012673


def test_the_reasoning_requirement_is_remembered_per_model(monkeypatch):
    """The endpoint's answer does not change between two calls.

    Without the memo the 400 is re-provoked on EVERY call — 60 wasted round trips over one
    benchmark run, on the classification that sits on a run's critical path.
    """
    import urllib.error

    sent = []

    def fake_urlopen(request, *_args, **_kwargs):
        body = json.loads(request.data.decode("utf-8"))
        sent.append(body["reasoning"])
        if body["reasoning"] == {"enabled": False}:
            raise urllib.error.HTTPError(
                url="https://openrouter.ai", code=400, msg="Bad Request", hdrs=None,
                fp=io.BytesIO(
                    json.dumps({"error": {"message": "Reasoning is mandatory."}}).encode()
                ),
            )
        return _Response(
            {
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
                "model": "test/model",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    service = AIService(api_key="test-key")

    for _ in range(3):
        service._call_openrouter("test/model", [{"role": "user", "content": "hello"}])

    # First call pays the refusal; the two after it go straight to the accepted form.
    assert sent == [
        {"enabled": False}, {"effort": "minimal"},
        {"effort": "minimal"},
        {"effort": "minimal"},
    ]
