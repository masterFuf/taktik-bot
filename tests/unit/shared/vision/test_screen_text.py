import base64
import inspect
import io
import threading
import time

from PIL import Image

from taktik.core.shared.vision.screen_text import screenshot_pil


def _png_b64():
    buffer = io.BytesIO()
    Image.new("RGB", (12, 8), "blue").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _JsonRpc:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def takeScreenshot(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.result


class _U2Device:
    def __init__(self, rpc):
        self.jsonrpc = rpc
        self.unbounded_calls = 0

    def screenshot(self, **_kwargs):
        self.unbounded_calls += 1
        raise AssertionError("unbounded screenshot fallback must not run")


def test_u2_screenshot_uses_bounded_jsonrpc_call():
    rpc = _JsonRpc(result=_png_b64())
    device = _U2Device(rpc)

    image = screenshot_pil(device, timeout_seconds=2.5)

    assert image.size == (12, 8)
    assert rpc.calls == [((1, 80), {"http_timeout": 2.5})]
    assert device.unbounded_calls == 0


def test_u2_screenshot_failure_does_not_retry_with_global_timeout():
    rpc = _JsonRpc(error=TimeoutError("slow device"))
    device = _U2Device(rpc)

    assert screenshot_pil(device) is None
    assert device.unbounded_calls == 0


def test_whole_screen_text_operation_has_a_wall_clock_boundary(monkeypatch):
    release = threading.Event()

    def stalled_screenshot(*_args, **_kwargs):
        release.wait(10)
        return None

    monkeypatch.setattr(
        "taktik.core.shared.vision.screen_text.screenshot_pil",
        stalled_screenshot,
    )
    monkeypatch.setattr(
        "taktik.core.shared.vision.screen_text.OcrService.prepare",
        lambda: True,
    )
    started_at = time.monotonic()

    from taktik.core.shared.vision.screen_text import locate_text_on_screen

    matches = locate_text_on_screen(
        object(),
        "more",
        operation_timeout_seconds=0.03,
    )
    elapsed = time.monotonic() - started_at
    release.set()

    assert matches == []
    assert elapsed < 0.3


def test_native_ocr_dependencies_are_prepared_before_worker_starts(monkeypatch):
    caller_thread = threading.get_ident()
    calls = []

    monkeypatch.setattr(
        "taktik.core.shared.vision.screen_text.OcrService.prepare",
        lambda: calls.append(("prepare", threading.get_ident())) or True,
    )
    monkeypatch.setattr(
        "taktik.core.shared.vision.screen_text.screenshot_pil",
        lambda *_args, **_kwargs: Image.new("RGB", (20, 20), "black"),
    )
    monkeypatch.setattr(
        "taktik.core.shared.vision.screen_text.OcrService.locate",
        lambda *_args, **_kwargs: calls.append(("locate", threading.get_ident())) or [],
    )

    from taktik.core.shared.vision.screen_text import locate_text_on_screen

    assert locate_text_on_screen(object(), "plus") == []
    assert calls[0] == ("prepare", caller_thread)
    assert calls[1][0] == "locate"
    assert calls[1][1] != caller_thread


def test_default_ocr_wall_budget_covers_screenshot_and_tesseract_budgets():
    from taktik.core.shared.vision.screen_text import locate_text_on_screen

    parameters = inspect.signature(locate_text_on_screen).parameters
    screenshot_budget = parameters["screenshot_timeout_seconds"].default
    ocr_budget = parameters["ocr_timeout_seconds"].default
    total_budget = parameters["operation_timeout_seconds"].default

    assert total_budget >= screenshot_budget + ocr_budget + 2.0
