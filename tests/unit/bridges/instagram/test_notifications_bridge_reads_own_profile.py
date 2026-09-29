"""The notifications scan reads our own profile on the phone its bridge connected.

Seen on the desktop bridge: the scan's first step, `own_profile`, ended on "Could not read your
profile", with "'Device' object has no attribute 'batch_xpath_check'" in the log. The bridge's base
exposes the shared device facade, and an Instagram action kept any facade it was handed as it was,
instead of its own: the reader of our profile asked the shared one for what only Instagram's has
(`batch_xpath_check`, the package in `app_id`). The Lab hid it: its actions hand the workflows its own
Instagram facade.

The path is the bridge's: its connection (`_connect`, the real `InstagramDeviceBase.connect()`, on the
phone a host hands it), then the scan's step (`_refresh_own_account`). The screens are real dumps of
Instagram 410 in French, anonymized: the home feed (`ig410_fr_home_feed.xml`, Pixel 3) and our own
profile (`ig410_fr_own_profile_with_suggestions.xml`, Pixel 3a); a tap on the tab bar shows the
screen of the tab it lands on.
"""

import re
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.app_manager as app_manager
import taktik.core.database as database
import taktik.core.shared.device.connection as connection
from taktik.core.shared.device.connected_device import ConnectedDevice
from bridges.instagram.notifications import commands as bridge_commands
from taktik.core.social_media.instagram.workflows.management.notifications import commands
from taktik.core.social_media.instagram.workflows.management.notifications import agent_handler
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
HOME = (FIXTURES / "ig410_fr_home_feed.xml").read_text(encoding="utf-8")
OWN_PROFILE = (FIXTURES / "ig410_fr_own_profile_with_suggestions.xml").read_text(encoding="utf-8")
#: The screen a tab of the tab bar shows.
TABS = {f"{PKG}:id/feed_tab": HOME, f"{PKG}:id/profile_tab": OWN_PROFILE}


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


#: uiautomator's `d(**selector)` keys this step asks, read off the dump (the clone proxy asks every
#: id as `resourceIdMatches`, the whole id matching).
_UI_SELECTOR = {
    "resourceId": lambda node, value: node.get("resource-id") == value,
    "resourceIdMatches": lambda node, value: re.fullmatch(value, node.get("resource-id") or "") is not None,
    "text": lambda node, value: node.get("text") == value,
    "description": lambda node, value: node.get("content-desc") == value,
}


class _Selection:
    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    def get_text(self):
        return self._nodes[0].get("text") if self._nodes else None

    @property
    def info(self):
        return {"text": self.get_text()}


class _Phone:
    """uiautomator2 on the two captures: its xpath engine, `d(...)` and taps read off the screen shown."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2220}

    def __init__(self):
        self.screen = HOME
        self.taps = []
        self.xpath = XPathEntry(self)

    def _nodes(self):
        return list(etree.fromstring(self.screen.encode("utf-8")).iter("node"))

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def app_current(self):
        return {"package": PKG}

    def __call__(self, **selector):
        return _Selection([node for node in self._nodes()
                           if all(_UI_SELECTOR[key](node, value) for key, value in selector.items())])

    def click(self, x, y):
        self.taps.append((x, y))
        for node in self._nodes():
            shown = TABS.get(node.get("resource-id"))
            left, top, right, bottom = _bounds(node) if shown else (0, 0, -1, -1)
            if left <= x <= right and top <= y <= bottom:
                self.screen = shown
                return

    def long_click(self, x, y, duration=None):
        self.click(x, y)

    def press(self, key):
        return True

    def screenshot(self, *_a, **_k):
        from PIL import Image

        return Image.new("RGB", (1080, 2220))


def _bridge_phone(monkeypatch, tmp_path) -> _Phone:
    """The phone above behind the bridge's connection, and a base of its own for the run."""
    import time

    phone = _Phone()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "notifications.db"))
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    monkeypatch.setattr(connection, "ConnectionService",
                        lambda device_id: ConnectedDevice(SimpleNamespace(device=phone), device_id))
    # The installed version is read by adb; this phone has none, and the selectors stay the base.
    monkeypatch.setattr(app_manager.AppService, "get_installed_version", lambda self: None)
    return phone


@pytest.fixture
def bridge_runtime(monkeypatch, tmp_path):
    """The notifications bridge connected the way the desktop connects it, on the phone above."""
    phone = _bridge_phone(monkeypatch, tmp_path)
    runtime = bridge_commands._connect("phone-1", None, restart=False)
    return runtime, phone


def test_the_scan_reads_our_own_profile_on_the_bridge_s_phone(bridge_runtime):
    runtime, phone = bridge_runtime
    events = []
    host = commands.NotificationsHost(connect=lambda restart: runtime, emit=events.append)

    account = commands._refresh_own_account(host, runtime, None)

    steps = [(e["step"], e["step_status"]) for e in events if e["type"] == "notification_step"]
    assert steps == [("own_profile", "running"), ("own_profile", "done")]
    assert account == "user_4"
    assert [e for e in events if e["type"] == "active_account"] == [
        {"type": "active_account", "username": "user_4", "followers": 22, "following": 57, "posts": 1}]
    # Back on the feed, where the activity entry lives.
    assert phone.screen is HOME


def test_the_counters_the_scan_reads_on_the_bridge_are_written_to_the_base(monkeypatch, tmp_path):
    """Seen on the Pixel 4a: the step read the counters, then "Database service not configured":
    the other bridges configure the base in their session, this one never did.

    The whole path of the bridge: its command (`run_notifications_command`, a new bridge process:
    no base configured), the core launcher (`run_instagram_notifications`), and the scan cut down
    to its first step, `_refresh_own_account` on the bridge's connection, as `cmd_scan` calls it
    (the connection without the restart: this phone cannot relaunch Instagram)."""
    import sqlite3

    _bridge_phone(monkeypatch, tmp_path)
    monkeypatch.setattr(database, "db_service", None)
    events = []

    def scan_first_step(host, limit, **_options):
        runtime = host.connect(False)
        commands._refresh_own_account(host, runtime, None)
        return {"success": True}

    monkeypatch.setattr(commands, "cmd_scan", scan_first_step)
    monkeypatch.setattr(bridge_commands, "emit_notif_json", lambda payload, flush=False: events.append(payload))
    assert agent_handler.run_instagram_notifications is bridge_commands.run_instagram_notifications

    bridge_commands.run_notifications_command({"deviceId": "phone-1", "command": "scan", "scroll": 0})

    steps = [(e["step"], e["step_status"]) for e in events if e.get("type") == "notification_step"]
    assert steps == [("own_profile", "running"), ("own_profile", "done")]
    with sqlite3.connect(tmp_path / "notifications.db") as base:
        row = base.execute("SELECT followers_count, following_count, posts_count FROM instagram_profiles "
                           "WHERE username = ?", ("user_4",)).fetchone()
    assert row == (22, 57, 1)
