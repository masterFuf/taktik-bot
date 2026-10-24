"""A uiautomator2 server that answers a call with an error of its own is alive: no repair.

Pixel 6 Pro, Android 17, 2026-10-24: the server answers `deviceInfo` with
`java.lang.IllegalStateException: ApplicationSharedMemory not initialized` (its `UiDevice` cannot
open a window context to read the display size), while every other call works and the run goes
on. The health check read `deviceInfo`, took the answer for a dead agent, reset uiautomator twice
and logged ERROR « ATX agent repair failed » before each run (about 8 s lost).

The answer here is the phone's, kept in `fixtures/u2_device_info_android17_pixel6pro.json`, and
goes through uiautomator2's own JSON-RPC reader (`uiautomator2.core._jsonrpc_call`): the test sees
the exception uiautomator2 raises on that phone.
"""

import json
from typing import Any, cast

from uiautomator2 import core as u2_core
from uiautomator2.exceptions import HTTPError

from taktik.core.shared.device import manager as manager_module
from taktik.core.shared.device.manager import DeviceManager
from unit.paths import CORE

ANDROID_17_DEVICE_INFO = (CORE / "tests/unit/shared/device/fixtures/u2_device_info_android17_pixel6pro.json").read_text(
    encoding="utf-8")


class _Response:
    """What `_http_request` hands `_jsonrpc_call`: the server's JSON body."""

    def __init__(self, body: str):
        self.text = body

    def json(self):
        return json.loads(self.text)


class _Device:
    """A uiautomator2 device whose `info` asks the server for `deviceInfo`, as uiautomator2 does."""

    @property
    def info(self):
        # No adb device: `_http_request`, the one place it is used, is replaced by the phone's answer.
        return u2_core._jsonrpc_call(cast(Any, None), 9008, "deviceInfo", {}, 10, False)


def _manager(monkeypatch, answer):
    monkeypatch.setattr(u2_core, "_http_request", answer)
    monkeypatch.setattr(manager_module.time, "sleep", lambda _s: None)
    manager = DeviceManager("emulator-5554")
    manager.device = _Device()
    repairs = []
    monkeypatch.setattr(manager, "_repair_atx", lambda: repairs.append("repair") or True)
    return manager, repairs


def test_the_android_17_answer_to_device_info_is_a_live_agent(monkeypatch):
    manager, repairs = _manager(monkeypatch, lambda *_a, **_k: _Response(ANDROID_17_DEVICE_INFO))
    errors = []
    sink = manager_module.logger.add(lambda message: errors.append(str(message)), level="ERROR")
    try:
        assert manager._verify_and_repair_atx() is True
    finally:
        manager_module.logger.remove(sink)
    assert repairs == []
    assert errors == []


def test_an_agent_that_does_not_answer_is_still_repaired(monkeypatch):
    def refused(*_a, **_k):
        raise HTTPError("HTTP request failed: connection refused")

    manager, repairs = _manager(monkeypatch, refused)
    assert manager._verify_and_repair_atx(max_retries=2) is False
    assert repairs == ["repair", "repair"]


def test_the_check_says_what_the_phone_refused(monkeypatch):
    manager, _repairs = _manager(monkeypatch, lambda *_a, **_k: _Response(ANDROID_17_DEVICE_INFO))
    said = []
    sink = manager_module.logger.add(lambda message: said.append(str(message)), level="INFO")
    try:
        healthy, error = manager._check_atx_health()
    finally:
        manager_module.logger.remove(sink)
    assert (healthy, error) == (True, None)
    assert any("ApplicationSharedMemory not initialized" in line for line in said)

