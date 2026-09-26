"""A 429 is the one HTTP failure that says what to do: retry shortly.

It used to be returned as a plain failure, which silently threw the generation away. Measured
on 2026-09-10: 0 rate limits across 396 production calls on qwen, and repeated ones the moment
calls were fired back to back -- which is what 200 accounts running in parallel look like.
"""

import io
import json
import urllib.error
import urllib.request

from taktik.core.app.ai.providers import openrouter
from taktik.core.app.ai.providers.openrouter import AIService


def _http_error(code, body="rate-limited upstream. Please retry shortly"):
    return urllib.error.HTTPError(
        openrouter.OPENROUTER_API_URL, code, "err", {}, io.BytesIO(body.encode())
    )


class _Ok:
    def __init__(self):
        self._body = json.dumps({
            "model": "qwen/qwen3.7-flash",
            "choices": [{"message": {"content": "une vraie reponse"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.00001},
        }).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run(monkeypatch, outcomes):
    """Drive one call through a scripted sequence of HTTP outcomes; return (result, waits)."""
    queue = list(outcomes)
    waits = []
    monkeypatch.setattr(openrouter.time, "sleep", lambda s: waits.append(s))

    def fake_urlopen(request, timeout=None):
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    # `_call_openrouter` imports urllib inside the function, so the stdlib module is
    # what its local name resolves to -- patching it there reaches the call.
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    service = AIService(api_key="x" * 10)
    result = service._call_openrouter(
        "qwen/qwen3.7-flash", [{"role": "user", "content": "hi"}], 0.0, 20, label="t"
    )
    return result, waits


def test_a_burst_that_clears_is_recovered(monkeypatch):
    """The common case: one or two 429s, then the upstream answers."""
    result, waits = _run(monkeypatch, [_http_error(429), _Ok()])

    assert result["success"] is True
    assert result["text"] == "une vraie reponse"
    assert waits == [openrouter.RATE_LIMIT_BACKOFF_SECONDS[0]]


def test_the_waits_grow_and_are_bounded(monkeypatch):
    """Two waits, growing, then give up -- a third would hold a run hostage to an upstream that
    is saturated for longer than a burst."""
    result, waits = _run(monkeypatch, [_http_error(429)] * 5)

    assert result["success"] is False
    assert result["rate_limited"] is True
    assert waits == list(openrouter.RATE_LIMIT_BACKOFF_SECONDS)
    assert waits == sorted(waits)


def test_a_transient_gateway_error_is_retried_like_a_rate_limit(monkeypatch):
    """503 (no provider available) and 502 (bad upstream answer) are not billed and clear
    like a burst; they get the same two waits."""
    result, waits = _run(monkeypatch, [_http_error(503, "no provider available"), _Ok()])

    assert result["success"] is True
    assert waits == [openrouter.RATE_LIMIT_BACKOFF_SECONDS[0]]

    result, waits = _run(monkeypatch, [_http_error(502, "bad gateway")] * 5)

    assert result["success"] is False
    assert result["rate_limited"] is False
    assert waits == list(openrouter.RATE_LIMIT_BACKOFF_SECONDS)


def test_another_http_error_is_never_retried(monkeypatch):
    """A quota or a malformed request must stay one call: retrying only doubles the wait."""
    result, waits = _run(monkeypatch, [_http_error(402, "insufficient credits"), _Ok()])

    assert result["success"] is False
    assert result["rate_limited"] is False
    assert waits == []
