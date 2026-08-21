"""Every paid model call reports its cost — once, from the transport.

The session AI cost (and the Analytics tile that sums it) used to be built by adding the
`cost_usd` carried on the per-CARD events: `ai_profile_done`, `ai_screenshot_done`,
`ai_comment_done`. Those only fire on paths that produce a card, so anything paid for
without one was invisible: a declined smart comment, a declined in-thread reply, a batch
username classification, an agent decision. `_call_openrouter` is the single point every
paid call passes through, so that is where the ledger belongs.
"""

import json as _json
import urllib.request as _urllib

from taktik.core.app.ai.providers.openrouter import AIService


class _RecordingIpc:
    """Captures the wire events an AIService emits."""

    def __init__(self):
        self.events = []

    def ai_spend(self, cost_usd, model=None, label=None, kind="other"):
        self.events.append({"type": "ai_spend", "cost_usd": cost_usd,
                            "model": model, "label": label, "kind": kind})


def _service_with_response(payload, ipc=None):
    service = AIService(api_key="test-key")
    service.ipc = ipc

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        @staticmethod
        def read():
            return _json.dumps(payload).encode()

    return service, lambda _request, **_kw: _Resp()


def _call(service, fake_urlopen, **kwargs):
    original = _urllib.urlopen
    _urllib.urlopen = fake_urlopen
    try:
        return service._call_openrouter("google/gemini-3.1-flash-lite", [], **kwargs)
    finally:
        _urllib.urlopen = original


_OK = {
    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
    "model": "google/gemini-3.1-flash-lite",
    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.00042},
}


def test_a_paid_call_reports_its_spend():
    ipc = _RecordingIpc()
    service, fake = _service_with_response(_OK, ipc)
    result = _call(service, fake, label="engagement_verdict @x", kind="verdict")

    assert result["cost_usd"] == 0.00042
    assert ipc.events == [{
        "type": "ai_spend", "cost_usd": 0.00042,
        "model": "google/gemini-3.1-flash-lite", "label": "engagement_verdict @x",
        "kind": "verdict",
    }]


def test_spend_is_reported_even_when_the_caller_shows_no_card():
    """The whole point: a call whose outcome produces no Agent card still costs money."""
    ipc = _RecordingIpc()
    service, fake = _service_with_response(_OK, ipc)
    # No `label`, nothing downstream — a batch classification or a declined comment.
    _call(service, fake)

    assert len(ipc.events) == 1
    assert ipc.events[0]["cost_usd"] == 0.00042


def test_a_failed_call_reports_nothing():
    ipc = _RecordingIpc()
    service, _ = _service_with_response(_OK, ipc)

    def boom(_request, **_kw):
        raise RuntimeError("network down")

    result = _call(service, boom)
    assert result["success"] is False
    assert ipc.events == []


def test_a_response_without_a_cost_reports_nothing():
    ipc = _RecordingIpc()
    payload = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "model": "google/gemini-3.1-flash-lite",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }
    service, fake = _service_with_response(payload, ipc)
    _call(service, fake)
    assert ipc.events == []


def test_standalone_bot_without_ipc_still_completes_the_call():
    service, fake = _service_with_response(_OK, None)
    assert _call(service, fake)["success"] is True


def test_a_broken_ipc_never_breaks_the_call():
    class _Exploding:
        def ai_spend(self, *_a, **_k):
            raise RuntimeError("pipe closed")

    service, fake = _service_with_response(_OK, _Exploding())
    assert _call(service, fake)["success"] is True


def test_an_unknown_kind_never_invents_a_bucket():
    """A typo at a call site must land in `other`, not create a category of its own."""
    ipc = _RecordingIpc()
    service, fake = _service_with_response(_OK, ipc)
    _call(service, fake, kind="comnent")
    assert ipc.events[0]["kind"] == "other"


def test_every_paid_call_site_declares_a_kind():
    """The breakdown is only honest if nothing silently falls into `other`.

    Guards against the real failure mode: a new generator is added, nobody threads a kind,
    and its spend quietly joins the unlabelled bucket while the tile still looks complete.
    """
    import inspect
    import re

    from taktik.core.app.ai.providers import openrouter as provider
    from taktik.core.app.ai.comments import generation

    for module in (provider, generation):
        source = inspect.getsource(module)
        for match in re.finditer(r"self\.(?:text_completion|vision_completion|vision_json_completion)\(", source):
            tail = source[match.end():match.end() + 600]
            depth, end = 1, 0
            for i, ch in enumerate(tail):
                depth += (ch == "(") - (ch == ")")
                if depth == 0:
                    end = i
                    break
            call = tail[:end]
            assert "kind=" in call, (
                f"a paid call in {module.__name__} declares no spend kind: {call[:120]}"
            )
