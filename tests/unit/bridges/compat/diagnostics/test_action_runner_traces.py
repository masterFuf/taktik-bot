from pathlib import Path

import re

from bridges.compat.diagnostics.runtime.action_test import runner as action_runner
from bridges.compat.diagnostics.runtime.action_test import session as action_session
from bridges.compat.diagnostics.runtime.action_test import tracing as action_tracing
from bridges.compat.diagnostics.runtime.action_test.tracing import SelectorTracer, TracedSelector


class _FakeSelector:
    def __init__(self, exists: bool):
        self._exists = exists

    @property
    def exists(self) -> bool:
        return self._exists


class _FakeRawDevice:
    info = {
        "productName": "Oukitel C57 S",
        "brand": "Oukitel",
        "release": "14",
        "displayDensity": 420,
        "scaledDensity": 2.75,
    }

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "MainActivity"}


class _FakeDevice:
    _device = _FakeRawDevice()

    def get_screen_size(self):
        return 1080, 2340

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


class _HomeAndPostDetection:
    def is_story_viewer_open(self):
        return False

    def is_on_profile_screen(self):
        return False

    def is_on_home_screen(self):
        return True

    def is_on_search_screen(self):
        return False

    def is_on_post_screen(self):
        return True


class _ProfileAndHomeDetection:
    def is_story_viewer_open(self):
        return False

    def is_on_profile_screen(self):
        return True

    def is_on_home_screen(self):
        return True

    def is_on_search_screen(self):
        return False

    def is_on_post_screen(self):
        return False


class _HomeAndPostBundle:
    def __init__(self):
        self.device = _FakeDevice()
        self.detection = _HomeAndPostDetection()


class _ProfileAndHomeBundle:
    def __init__(self):
        self.device = _FakeDevice()
        self.detection = _ProfileAndHomeDetection()


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


def test_selector_tracer_reset_clears_action_context():
    tracer = SelectorTracer()
    tracer.set_action_context("navigation.go_home")
    tracer.set_screen("instagram.home")
    tracer.record("//*[@resource-id='x']", False)

    tracer.reset()
    tracer.record("//*[@resource-id='y']", True)

    assert len(tracer.traces) == 1
    assert tracer.traces[0]["screen"] == "unknown"
    assert "family" not in tracer.traces[0]


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
    assert isinstance(payload["phase_timings"]["actionMs"], float)
    assert isinstance(payload["phase_timings"]["screenBeforeMs"], float)
    assert isinstance(payload["phase_timings"]["screenAfterMs"], float)


def test_execute_action_without_artifacts_stays_light(monkeypatch):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)
    monkeypatch.setattr(
        action_runner,
        "build_artifact_context",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("artifact context should not be built")),
    )

    bundle = _FakeBundle()

    def run_action(fake_bundle, params):
        fake_bundle.state = "after"
        return True

    action_runner._execute_action(
        {"navigation.open_profile": run_action},
        "navigation.open_profile",
        bundle,
        {},
        SelectorTracer(),
    )

    assert emitted[0]["artifacts"] is None


def test_execute_action_marks_expected_screen_mismatch(monkeypatch):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)

    bundle = _FakeBundle()

    def run_action(fake_bundle, params):
        fake_bundle.state = "after"
        return True

    action_runner._execute_action(
        {"navigation.go_home": run_action},
        "navigation.go_home",
        bundle,
        {},
        SelectorTracer(),
    )

    transition = emitted[0]["transition"]
    assert transition["expectedScreenAfter"] == "instagram.home"
    assert transition["actualScreenAfter"] == "instagram.profile"
    assert transition["ok"] is False
    assert transition["reason"] == "screen_mismatch"


def test_execute_action_includes_request_id(monkeypatch):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)

    bundle = _FakeBundle()

    action_runner._execute_action(
        {"detection.get_current_screen": lambda fake_bundle, params: True},
        "detection.get_current_screen",
        bundle,
        {},
        SelectorTracer(),
        request_id="req-1",
    )

    assert emitted[0]["request_id"] == "req-1"


def test_execute_action_session_error_does_not_exit(monkeypatch):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)

    bundle = _FakeBundle()

    def raise_action(fake_bundle, params):
        raise RuntimeError("boom")

    action_runner._execute_action(
        {"detection.get_current_screen": raise_action},
        "detection.get_current_screen",
        bundle,
        {},
        SelectorTracer(),
        request_id="req-error",
        exit_on_error=False,
    )

    assert emitted[0]["request_id"] == "req-error"
    assert emitted[0]["success"] is False
    assert "Exception: boom" in emitted[0]["message"]
    assert isinstance(emitted[0]["phase_timings"]["actionMs"], float)


def test_execute_action_captures_lab_artifacts(monkeypatch, tmp_path):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)
    monkeypatch.setattr(action_runner, "_BOT_ROOT", tmp_path)
    monkeypatch.setattr(
        "bridges.compat.diagnostics.runtime.action_test.artifacts._resolve_app_version",
        lambda device_id, package_name, platform: "410.0.0.53.71",
    )

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
        device_id="device-1",
        mode="lab",
        capture_artifacts=True,
        language_optimization={
            "platform": "instagram",
            "language": "fr",
            "applied": True,
            "reason": None,
            "timingMs": 12.3,
        },
    )

    artifacts = emitted[0]["artifacts"]
    assert artifacts["xmlBefore"].endswith("before.xml")
    assert artifacts["xmlAfter"].endswith("after.xml")
    assert artifacts["screenshotBefore"].endswith("before.png")
    assert artifacts["screenshotAfter"].endswith("after.png")
    assert artifacts["report"].endswith("report.json")
    assert artifacts["analysis"].endswith("analysis.json")
    assert "\\device-1\\instagram\\410.0.0.53.71\\action-runs\\post.like\\" in artifacts["report"]

    for path in artifacts.values():
        assert Path(path).exists()

    assert "<hierarchy>" not in str(emitted[0])

    report = Path(artifacts["report"]).read_text(encoding="utf-8")
    assert '"selectorHealth"' in report
    assert '"resolution"' in report
    assert '"densityDpi": 420' in report
    assert '"language": "fr"' in report
    assert '"languageOptimization"' in report
    assert '"model": "Oukitel C57 S"' in report
    assert '"phaseTimings"' in report
    assert '"transition"' in report
    assert '"version": "410.0.0.53.71"' in report

    analysis = Path(artifacts["analysis"]).read_text(encoding="utf-8")
    assert '"recommendations"' in analysis
    assert '"selectorSummary"' in analysis


def test_selector_tracer_resolves_selector_id_when_unambiguous(monkeypatch):
    monkeypatch.setitem(
        action_tracing._XPATH_ID_INDEX_CACHE,
        "instagram",
        {"//x": "navigation.home_tab"},
    )
    tracer = SelectorTracer(app="instagram")
    tracer.record("//x", True)
    tracer.record("//unknown", False)

    assert tracer.traces[0]["selectorId"] == "navigation.home_tab"
    assert "selectorId" not in tracer.traces[1]


def test_selector_tracer_without_app_skips_selector_id(monkeypatch):
    monkeypatch.setitem(
        action_tracing._XPATH_ID_INDEX_CACHE,
        "instagram",
        {"//x": "navigation.home_tab"},
    )
    tracer = SelectorTracer()
    tracer.record("//x", True)

    assert "selectorId" not in tracer.traces[0]


def test_build_xpath_index_is_unambiguous_and_namespaced():
    from taktik.core.compat.selectors.setup import build_xpath_to_selector_id_index

    index = build_xpath_to_selector_id_index("instagram")
    assert isinstance(index, dict) and index
    for xpath, selector_id in index.items():
        assert isinstance(xpath, str) and xpath
        assert isinstance(selector_id, str) and "." in selector_id


def test_execute_action_perf_fast_skips_media_but_keeps_report(monkeypatch, tmp_path):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)
    monkeypatch.setattr(action_runner, "_BOT_ROOT", tmp_path)
    monkeypatch.setattr(
        "bridges.compat.diagnostics.runtime.action_test.artifacts._resolve_app_version",
        lambda device_id, package_name, platform: "410.0.0.53.71",
    )

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
        device_id="device-1",
        mode="lab",
        capture_artifacts=True,
        perf_fast=True,
    )

    artifacts = emitted[0]["artifacts"]
    # Report is still produced (timings persisted) but no XML/PNG capture happened.
    assert artifacts["report"].endswith("report.json")
    assert "xmlBefore" not in artifacts
    assert "screenshotBefore" not in artifacts
    assert emitted[0]["perf_fast"] is True
    assert "artifactsBeforeMs" not in emitted[0]["phase_timings"]

    report = Path(artifacts["report"]).read_text(encoding="utf-8")
    assert '"perfFast": true' in report


def test_execute_action_session_cache_reused_across_runs(monkeypatch, tmp_path):
    emitted = []
    monkeypatch.setattr(action_runner, "emit", emitted.append)
    monkeypatch.setattr(action_runner, "_BOT_ROOT", tmp_path)

    version_calls = []

    def fake_version(device_id, package_name, platform):
        version_calls.append(package_name)
        return "410.0.0.53.71"

    monkeypatch.setattr(
        "bridges.compat.diagnostics.runtime.action_test.artifacts._resolve_app_version",
        fake_version,
    )

    cache = action_session._SessionContextCache()

    def run_action(fake_bundle, params):
        fake_bundle.state = "after"
        return True

    for _ in range(2):
        bundle = _FakeBundle()
        action_runner._execute_action(
            {"post.like": run_action},
            "post.like",
            bundle,
            {},
            SelectorTracer(),
            platform="instagram",
            device_id="device-1",
            mode="lab",
            capture_artifacts=True,
            session_context_cache=cache,
        )

    # The session-invariant context (hence app version resolution) is resolved once.
    assert len(version_calls) == 1
    assert cache.value is not None


def test_action_artifacts_use_bot_debug_ui_root():
    expected_bot_root = Path(action_runner.__file__).resolve().parents[5]

    assert action_runner._BOT_ROOT == expected_bot_root
    assert action_runner._artifact_dir(
        "instagram",
        "run-1",
        device_id="device-1",
        app_version="410.0.0.53.71",
        action_id="navigation.go_home",
    ) == (
        expected_bot_root
        / "debug_ui"
        / "cartography"
        / "device-1"
        / "instagram"
        / "410.0.0.53.71"
        / "action-runs"
        / "navigation.go_home"
        / "run-1"
    )


def test_build_run_id_uses_readable_utc_timestamp():
    run_id = action_runner._build_run_id("navigation.go_home")

    assert re.match(r"^navigation.go_home_\d{8}T\d{9}Z$", run_id)


def test_detect_screen_prefers_home_over_feed_post_indicators():
    assert action_runner._detect_screen(_HomeAndPostBundle()) == "instagram.home"


def test_detect_screen_prefers_profile_over_selected_home_tab():
    assert action_runner._detect_screen(_ProfileAndHomeBundle()) == "instagram.profile"
