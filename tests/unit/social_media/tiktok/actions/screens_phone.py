"""A TikTok phone made of real captures, for the tests of the actions that tap and read.

uiautomator2 as the production touches it: `d.xpath()` through uiautomator2's own engine on the
screen shown, `d(resourceIdMatches=...)` on the same dump, the taps and keys it injects. A tap
inside an area of a screen (or a back key on it) goes through a `Door`: to another capture, at once
or some seconds later, the screen before it, or a capture of the opening, showing meanwhile.

Time is the test's (`install_test_clock`): a dump costs `dump_s` seconds of it, the pauses of the
production move it, nothing sleeps. A door that never opens is `Door(screen, after_s=None)`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple, Union

from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions as activity_actions_module
import taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions as dm_actions_module
import taktik.core.social_media.tiktok.actions.base.base_action as tiktok_base_action
import taktik.core.social_media.tiktok.actions.base.device_facade as tiktok_facade
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"

#: The modules whose `time` the production of these actions reads.
CLOCKED_MODULES = (dm_actions_module, activity_actions_module, tiktok_base_action, shared_base_action,
                   snapshot_module, shared_facade, tiktok_facade)

#: A door's key: a screen and the xpath of the area a tap opens it from, or "back" for the back key.
DoorKey = Tuple[str, str]


def install_test_clock(monkeypatch) -> SimpleNamespace:
    """The test's clock in place of `time` in the modules of the production: `clock.now`, in seconds."""
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now,
                                perf_counter=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in CLOCKED_MODULES:
        monkeypatch.setattr(module, "time", fake_time)
    return clock


def read_captures(**files: str) -> Dict[str, str]:
    """{name: the XML of the capture}, from the file names of `fixtures/`."""
    return {name: (FIXTURES / file).read_text(encoding="utf-8") for name, file in files.items()}


def bounds(node) -> Tuple[int, int, int, int]:
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def node_of(xml: str, xpath: str):
    """The first node of `xpath` on a capture, read as the dump holds it (`node`, `class`)."""
    return etree.fromstring(xml.encode("utf-8")).xpath(xpath)[0]


@dataclass(frozen=True)
class Door:
    """Where a tap goes: `screen`, `after_s` seconds later (None: never), showing `meanwhile`
    until then (None: the screen the tap was made on)."""

    screen: str
    after_s: Optional[float] = 0.0
    meanwhile: Optional[str] = None


class Selection:
    """`d(resourceIdMatches=...)` as `_find_all_by_rid` asks it: `exists`, `count`, an index, the
    text, the bounds, a click."""

    def __init__(self, phone: "ScreensPhone", nodes: List):
        self._phone = phone
        self._nodes = nodes

    @property
    def exists(self) -> bool:
        return bool(self._nodes)

    @property
    def count(self) -> int:
        return len(self._nodes)

    def __getitem__(self, index):
        return Selection(self._phone, [self._nodes[index]])

    def get_text(self):
        return self._nodes[0].get("text")

    @property
    def info(self):
        left, top, right, bottom = bounds(self._nodes[0])
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

    def click(self):
        left, top, right, bottom = bounds(self._nodes[0])
        self._phone.click((left + right) // 2, (top + bottom) // 2)


class ScreensPhone:
    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, screens: Dict[str, str], first: str,
                 doors: Optional[Dict[DoorKey, Union[str, Door]]] = None, *,
                 clock: Optional[SimpleNamespace] = None, dump_s: float = 0.0,
                 package: str = "com.ss.android.ugc.trill", size: Tuple[int, int] = (576, 1280)):
        self.screens = screens
        self._screen = first
        self.doors = {key: door if isinstance(door, Door) else Door(door) for key, door in (doors or {}).items()}
        self.clock = clock or SimpleNamespace(now=0.0)
        self.dump_s = dump_s
        self.package = package
        self.size = size
        #: (screen, x, y) for a tap, (screen, "press", key) for a key, in order.
        self.taps: List[tuple] = []
        #: When each tap and key was made, on the test's clock.
        self.tap_times: List[float] = []
        #: When each dump started, on the test's clock.
        self.dumps: List[float] = []
        self._pending: Optional[Tuple[Door, float]] = None
        self.xpath = XPathEntry(self)

    @property
    def screen(self) -> str:
        """The screen shown now: a door's screen once its time has come, what shows meanwhile before."""
        if self._pending is not None:
            door, opened_at = self._pending
            if door.after_s is not None and self.clock.now >= opened_at + door.after_s:
                self._screen, self._pending = door.screen, None
            elif door.meanwhile is not None:
                return door.meanwhile
        return self._screen

    def dump_hierarchy(self, *_a, **_k):
        xml = self.screens[self.screen]
        self.dumps.append(self.clock.now)
        self.clock.now += self.dump_s
        return xml

    def app_current(self):
        return {"package": self.package, "activity": "demo.Activity"}

    def window_size(self):
        return self.size

    def __call__(self, resourceIdMatches):
        nodes = etree.fromstring(self.screens[self.screen].encode("utf-8")).iter("node")
        return Selection(self, [n for n in nodes if re.fullmatch(resourceIdMatches, n.get("resource-id") or "")])

    def inside(self, tap: tuple, screen: str, xpath: str) -> bool:
        """Did `tap` land on `screen`, inside the first node of `xpath` there?"""
        if tap[0] != screen or tap[1] == "press":
            return False
        left, top, right, bottom = bounds(node_of(self.screens[screen], xpath))
        return left <= tap[1] <= right and top <= tap[2] <= bottom

    def _go(self, key_or_tap) -> None:
        tap_screen = self.screen
        for (screen, area), door in self.doors.items():
            if screen != tap_screen:
                continue
            through = (area == "back") if key_or_tap == "back" else (
                area != "back" and self.inside((screen, *key_or_tap), screen, area))
            if through:
                self._pending = (door, self.clock.now)
                return

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        self.tap_times.append(self.clock.now)
        self._go((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key):
        self.taps.append((self.screen, "press", key))
        self.tap_times.append(self.clock.now)
        if key == "back":
            self._go("back")
