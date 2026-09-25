"""The screen-reading measurement is read-only, and says so when something tried to act.

The phone is a fake uiautomator2 device whose every call goes through `jsonrpc_call`, as the real
one does; the screen is invented (public repository).
"""

import json
import sys
import time
from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import measure_screen_reading as script  # noqa: E402

PKG = "com.zhiliaoapp.musically:id/"


def _node(cls, rid="", text="", desc="", children="", bounds="[0,0][100,100]"):
    return (f'<node class="android.widget.{cls}" resource-id="{PKG + rid if rid else ""}" text="{text}" '
            f'content-desc="{desc}" package="com.zhiliaoapp.musically" clickable="true" enabled="true" '
            f'bounds="{bounds}">{children}</node>')


VIDEO_WITH_A_CUT_CAPTION = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    + _node("FrameLayout", "long_press_layout", desc="Video", bounds="[0,0][1080,2400]", children=(
        _node("TextView", "title", text="demo_author", bounds="[40,1900][400,1950]")
        + _node("TextView", "desc", text="A caption that goes on and on... more", bounds="[40,1960][900,2100]")
        + _node("Button", "nhe", desc="Sound: original sound - demo_author", bounds="[900,2200][1040,2340]")
        + _node("Button", "f57", desc="Like video. 12 likes", bounds="[960,1200][1060,1300]",
                children=_node("ImageView", "f4u", bounds="[970,1210][1050,1290]"))
        + _node("TextView", "f4z", text="12", bounds="[960,1300][1060,1340]")
    ))
    + "</hierarchy>"
)


class FakeAdb:
    def __init__(self):
        self.commands = []

    def shell(self, command, **_kwargs):
        self.commands.append(command)
        return ""

    def shell2(self, command, **_kwargs):
        return self.shell(command)


class FakePhone:
    """A uiautomator2 device the way the guard sees it: every call is a server call."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.calls = []
        self.xpath = XPathEntry(self)
        self._dev = FakeAdb()

    def jsonrpc_call(self, method, params=None, timeout=10):
        self.calls.append(method)
        return self.xml if method == "dumpWindowHierarchy" else True

    def dump_hierarchy(self, *_a, **_k):
        return self.jsonrpc_call("dumpWindowHierarchy", (False, 50))

    def click(self, x, y):
        self.jsonrpc_call("click", (x, y))

    def long_click(self, x, y, duration=0.5):
        self.jsonrpc_call("click", (x, y, duration))

    def press(self, key):
        self.jsonrpc_call("pressKey", (key,))

    def shell(self, command, timeout=60):
        return self._dev.shell2(command, timeout=timeout)

    def app_current(self):
        self.shell(["dumpsys", "window"])
        return {"package": "com.zhiliaoapp.musically", "activity": "SplashActivity"}


@pytest.fixture
def fast_clock(monkeypatch):
    """The probes wait up to 2 s each for what is absent: a clock that jumps when they sleep."""
    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + max(seconds, 0.0)))


@pytest.fixture
def english():
    from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture
def costs():
    from taktik.core.shared.telemetry import clear_telemetry_sink, configure_telemetry_sink

    received = []
    configure_telemetry_sink(lambda metric: received.append(metric) if metric.category == "device_io" else None)
    yield received
    clear_telemetry_sink()


@pytest.mark.parametrize("command, refused", [
    ("input tap 10 20", True), (["input", "swipe", "1", "2", "3", "4"], True),
    ("am start -n com.zhiliaoapp.musically/.Main", True), ("monkey -p x 1", True),
    ("cmd statusbar expand", True), ("ime set com.x/.Ime", True), ("settings put secure a b", True),
    ("pm clear com.zhiliaoapp.musically", True), ("wm size 1080x2400", True),
    ("/system/bin/input keyevent 4", True),
    ("dumpsys window windows", False), (["dumpsys", "activity", "top"], False), ("getprop ro.x", False),
    ("pm list packages", False), ("settings get secure default_input_method", False), ("wm size", False),
    ("CLASSPATH=/data/local/tmp/u2.jar app_process / com.wetest.uiautomator.Console", False), ("", False),
])
def test_what_a_measurement_may_run_on_the_phone(command, refused):
    assert script.is_refused_command(command) is refused


def test_the_guard_refuses_gestures_and_lets_reads_through():
    phone = FakePhone(VIDEO_WITH_A_CUT_CAPTION)
    guard = script.ReadOnlyGuard().install(phone)
    try:
        assert phone.dump_hierarchy() == VIDEO_WITH_A_CUT_CAPTION
        phone.shell("dumpsys window windows")
        for gesture in (lambda: phone.click(1, 2), lambda: phone.press("back"),
                        lambda: phone.shell("input swipe 1 2 3 4"), lambda: phone._dev.shell("am start x")):
            with pytest.raises(script.ReadOnlyViolation):
                gesture()
    finally:
        guard.uninstall()
    assert phone.calls == ["dumpWindowHierarchy"]
    assert phone._dev.commands == ["dumpsys window windows"]
    assert len(guard.refused) == 4


def test_a_refusal_swallowed_by_production_is_still_counted():
    phone = FakePhone(VIDEO_WITH_A_CUT_CAPTION)
    guard = script.ReadOnlyGuard().install(phone)
    try:
        try:
            phone.click(1, 2)
        except Exception:
            pass  # what production loops do with any error
    finally:
        guard.uninstall()
    assert guard.refused == ["server call click"]


def test_the_guard_also_covers_the_bot_s_own_adb_shell_and_goes_away():
    from taktik.core.shared.device import adb as adb_module

    original = adb_module._run_adb_shell
    guard = script.ReadOnlyGuard().install(FakePhone(""))
    try:
        with pytest.raises(script.ReadOnlyViolation):
            adb_module.run_adb_shell("serial-x", "input keyevent 4")
    finally:
        guard.uninstall()
    assert adb_module._run_adb_shell is original and guard.refused == ["adb shell input keyevent 4"]


def _reads(phone):
    from types import SimpleNamespace

    from bridges.compat.diagnostics.runtime.action_test.runner import _detect_screen
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import PopupHandler

    detection = DetectionActions(phone)
    bundle = SimpleNamespace(detection=detection, device=detection.device)
    return detection, script.feed_reads(detection, PopupHandler(None, detection)), lambda: _detect_screen(bundle)


def test_the_feed_reads_touch_nothing_where_production_would_tap(fast_clock, english, costs):
    from taktik.core.shared.telemetry.device_io import instrument_device_io

    phone = FakePhone(VIDEO_WITH_A_CUT_CAPTION)
    instrument_device_io(phone)
    guard = script.ReadOnlyGuard().install(phone)
    try:
        detection, reads, screen_name = _reads(phone)
        records, results = script.measure_once(reads, screen_name, costs)
        assert guard.refused == []
        # Production reads the caption in full: it taps the cut English caption open.
        detection.get_video_info(light_if_ad=True)
        assert guard.refused == ["server call click"]
    finally:
        guard.uninstall()

    assert script.screen_kind(results) == "video"
    assert results["feed.video_info"]["author"] == "demo_author"
    steps = [record["step"] for record in records]
    assert steps == ["feed.popups", "feed.comments", "feed.suggestion", "feed.video_info", "lab.screen",
                     script.DECISION_STEP]
    decision = records[-1]
    assert decision["dumps"] == sum(r["dumps"] for r in records if r["step"].startswith("feed.")) > 0


def test_the_summary_reads_a_bridge_run_and_its_log(tmp_path):
    def decision(kind, total_ms, dumps):
        return {"type": "step_metric", "category": "device_io", "action": script.DECISION_STEP,
                "detail": {"kind": kind, "total_ms": total_ms, "dumps": dumps, "dump_ms": dumps * 250.0}}

    stdout = [decision("video", 11000, 37), decision("video", 12000, 38), decision("ad", 4600, 16),
              {"type": "step_metric", "category": "scroll", "action": "flick"},
              {"type": "status", "status": "running"}]
    run = tmp_path / "run.jsonl"
    run.write_text("\n".join(json.dumps(item) for item in stdout) + "\nnot json\n", encoding="utf-8")
    log = tmp_path / "run.log"
    log.write_text("x | WARNING | Same video detected 1 times: @demo\n", encoding="utf-8")

    text = script.summarize([str(run), str(log)])
    assert "3 feed turns" in text
    assert "video (66.7 per 100 turns)" in text and "ad (33.3 per 100 turns)" in text
    assert "scroll/flick" in text and "Same video detected" in text


def test_the_summary_reads_measurement_files(tmp_path):
    lines = [{"record": "context", "device": "serial-x", "label": "ad"},
             {"record": "step", "device": "serial-x", "label": "ad", "step": script.DECISION_STEP,
              "total_ms": 4600.0, "dumps": 16, "dump_ms": 4000.0},
             {"record": "sample", "device": "serial-x", "label": "ad", "kind": "ad", "refused": 0}]
    path = tmp_path / "measure.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")

    text = script.summarize([str(path)])
    assert f"serial-x/ad/{script.DECISION_STEP}" in text and "D 250 ms" in text
    assert "{'ad': 1}" in text and "refused by the read-only guard: 0" in text
