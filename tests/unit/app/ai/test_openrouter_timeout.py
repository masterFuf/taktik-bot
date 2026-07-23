import threading
import time

from taktik.core.app.ai.providers.openrouter import AIService


def test_openrouter_call_has_a_total_wall_clock_deadline(monkeypatch):
    release = threading.Event()

    def stalled_urlopen(*_args, **_kwargs):
        release.wait(10)
        raise AssertionError("released after caller deadline")

    monkeypatch.setattr("urllib.request.urlopen", stalled_urlopen)
    monkeypatch.setattr(
        "taktik.core.app.ai.providers.openrouter.OPENROUTER_TOTAL_TIMEOUT_SECONDS",
        0.03,
    )
    started_at = time.monotonic()

    result = AIService(api_key="test-key")._call_openrouter(
        "test/model",
        [{"role": "user", "content": "hello"}],
    )
    elapsed = time.monotonic() - started_at
    release.set()

    assert result["success"] is False
    assert "total deadline" in result["error"]
    assert elapsed < 0.3
