from pathlib import Path

from bridges.compat.diagnostics.runtime.action_test import runner as action_runner
from bridges.compat.diagnostics.runtime.action_test.tracing import SelectorTracer, TracedSelector


class _FakeSelector:
    def __init__(self, exists: bool):
        self._exists = exists

    @property
    def exists(self) -> bool:
        return self._exists


class _FakeRawDevice:
    def app_current(self):
        return {"package": "com.instagram.android", "activity": "MainActivity"}


class _FakeDevice:
    _device = _FakeRawDevice()

    def get_xml_dump(self):
        return "<hierarchy><node text='test' /></hierarchy>"

    def screenshot(self, path: str) -> bool:
        Path(path).write_bytes(b"fake-png")
        return True


class _FakeDetection:
    def __init__(self, bundle):
        self._bundle = bundle

    def is_story_viewer_open(self):
        return False

    def is_on_post_screen(self):
        return False

    def is_on_profile_screen(self):
        return self._bundle.state == "after"

    def is_on_search_screen(self):
        return False

    def is_on_home_screen(self):
        return self._bundle.state == "before"


class _FakeBundle:
    def __init__(self):
        self.state = "before"
        self.device = _FakeDevice()
        self.detection = _FakeDetection(self)


def test_traced_selector_records_front_contract_fields():
    tracer = SelectorTracer()
    tracer.set_action_context("post.like")
    tracer.set_screen("instagram.home")

    selector = TracedSelector(_FakeSelector(True), "//*[@content-desc='Like']", tracer)

    assert selector.exists is True
    assert len(tracer.traces) == 1
    trace = tracer.traces[0]
    assert trace["xpath"] == "//*[@content-desc='Like']"
    assert trace["found"] is True
    assert trace["source"] == "python"
    assert trace["screen"] == "instagram.home"
    assert trace["fallbackIndex"] == 0
    assert trace["family"] == "post"
    assert isinstance(trace["elapsedMs"], float)


def test_execute_action_emits_ui_action_trace(monkeypatch):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)

    bundle = _FakeBundle()
    tracer = SelectorTracer()
    tracer.record("fallback", False)
    tracer.traces[0]["fallbackIndex"] = 1

    def run_action(fake_bundle, params):
        fake_bundle.state = "after"
        return True

    action_runner._execute_action(
        {"navigation.open_profile": run_action},
        "navigation.open_profile",
        bundle,
        {},
        tracer,
    )

    assert len(emitted) == 1
    payload = emitted[0]
    assert payload["type"] == "result"
    assert payload["success"] is True
    assert payload["ui_action_trace"]["actionId"] == "navigation.open_profile"
    assert payload["ui_action_trace"]["intent"] == "navigation"
    assert payload["ui_action_trace"]["screenBefore"] == "instagram.home"
    assert payload["ui_action_trace"]["screenAfter"] == "instagram.profile"
    assert payload["ui_action_trace"]["fallbackUsed"] is True
    assert isinstance(payload["ui_action_trace"]["timingMs"], float)


def test_execute_action_captures_lab_artifacts(monkeypatch, tmp_path):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)
    monkeypatch.setattr(action_runner, "_BOT_ROOT", tmp_path)

    bundle = _FakeBundle()

    def run_action(fake_bundle, params):
        fake_bundle.state = "after"
        return True

    action_runner._execute_action(
        {"post.like": run_action},
        "post.like",
        bundle,
        {},
        SelectorTracer(),
        platform="instagram",
        capture_artifacts=True,
    )

    artifacts = emitted[0]["artifacts"]
    assert artifacts["xmlBefore"].endswith("before.xml")
    assert artifacts["xmlAfter"].endswith("after.xml")
    assert artifacts["screenshotBefore"].endswith("before.png")
    assert artifacts["screenshotAfter"].endswith("after.png")

    for path in artifacts.values():
        assert Path(path).exists()

    assert "<hierarchy>" not in str(emitted[0])


def test_action_artifacts_use_bot_debug_ui_root():
    expected_bot_root = Path(action_runner.__file__).resolve().parents[5]

    assert action_runner._BOT_ROOT == expected_bot_root
    assert action_runner._artifact_dir("instagram", "run-1") == (
        expected_bot_root / "debug_ui" / "cartography" / "instagram" / "action-runs" / "run-1"
    )
