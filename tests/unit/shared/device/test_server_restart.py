"""A dying uiautomator2 server must not fail a read, and must never replay a gesture."""

import http.client

import pytest

from taktik.core.shared.device import server_restart
from taktik.core.shared.device.server_restart import call_past_a_dying_server, retry_cut_reads


class _DyingServerDevice:
    """Cuts the first `cuts` calls the way a server killed by its launcher does."""

    def __init__(self, cuts=1):
        self.cuts = cuts
        self.calls = []
        self.restarts = []

    def jsonrpc_call(self, method, params=None, timeout=10):
        self.calls.append(method)
        if self.cuts:
            self.cuts -= 1
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return f"{method}-result"

    def stop_uiautomator(self, wait=True):
        self.restarts.append("stop")

    def start_uiautomator(self):
        self.restarts.append("start")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(server_restart.time, "sleep", lambda _s: None)


def test_a_cut_dump_is_read_again_on_a_restarted_server():
    device = _DyingServerDevice()
    assert retry_cut_reads(device) is True

    assert device.jsonrpc_call("dumpWindowHierarchy", [False, 50]) == "dumpWindowHierarchy-result"
    assert device.calls == ["dumpWindowHierarchy", "dumpWindowHierarchy"]
    assert device.restarts == ["stop", "start"]


def test_a_cut_gesture_is_never_replayed():
    device = _DyingServerDevice()
    retry_cut_reads(device)

    with pytest.raises(http.client.RemoteDisconnected):
        device.jsonrpc_call("click", [540, 1200])
    assert device.calls == ["click"]
    assert device.restarts == []


def test_every_read_only_method_changes_nothing_on_screen():
    gestures = {"click", "longClick", "swipe", "swipePoints", "drag", "dragTo", "injectInputEvent",
                "pressKey", "pressKeyCode", "setText", "clearTextField", "clearInputText", "gesture",
                "setClipboard", "pasteClipboard", "scrollTo", "scrollForward", "flingForward", "wakeUp"}
    assert not gestures & server_restart.READ_ONLY_METHODS


def test_wrapping_twice_keeps_one_retry():
    device = _DyingServerDevice(cuts=2)
    retry_cut_reads(device)
    retry_cut_reads(device)

    with pytest.raises(http.client.RemoteDisconnected):
        device.jsonrpc_call("deviceInfo")
    assert device.calls == ["deviceInfo", "deviceInfo"]


def test_a_device_without_server_control_is_left_as_it_is():
    device = object()
    assert retry_cut_reads(device) is False


def test_a_connection_cut_by_a_dying_server_is_tried_again():
    attempts = []

    def connect():
        attempts.append(1)
        if len(attempts) == 1:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return "device"

    assert call_past_a_dying_server(connect) == "device"
    assert len(attempts) == 2


def test_other_connection_failures_are_not_hidden():
    def connect():
        raise RuntimeError("adb: device offline")

    with pytest.raises(RuntimeError):
        call_past_a_dying_server(connect)
