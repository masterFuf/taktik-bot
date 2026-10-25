"""A phone that shows a real capture of an Instagram sheet, for the tests that close one.

uiautomator2 as the closers drive it: `d(**selector)` and `d.xpath(...)` read the capture on screen,
a selector's `click()` taps the centre of the element's bounds (as uiautomator2's does), and every
gesture is recorded, then shows the next screen of `after` (the last one stays). A drag injected as
a whole path (`jsonrpc.swipePoints`, the way the shared drag hands it to the device) is recorded
with its points, so a test sees where the finger went down, the way it went and where it lifted; a
coarse `swipe` is recorded as its two ends, the way Android receives it.

The screen size is the capture's own (its root node), never a size of another phone.
"""

import re

from uiautomator2.xpath import XPathEntry

from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"

_NODE = re.compile(r"<node\b[^>]*>")
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def attribute(tag, name):
    found = re.search(rf'\b{name}="([^"]*)"', tag)
    return found.group(1) if found else ""


def bounds_of(tag):
    return tuple(int(v) for v in _BOUNDS.search(attribute(tag, "bounds")).groups())


def node_with_id(xml, rid_suffix):
    """The first node of the capture whose resource-id ends with `rid_suffix`."""
    for tag in _NODE.findall(xml):
        if attribute(tag, "resource-id").endswith(rid_suffix):
            return tag
    raise AssertionError(f"no {rid_suffix} on this capture")


def centre_of(tag):
    left, top, right, bottom = bounds_of(tag)
    return (left + right) // 2, (top + bottom) // 2


def screen_size(xml):
    """The capture's screen: as far right and as low as its nodes reach (its windows, the status
    bar and the navigation bar among them, come in no fixed order)."""
    boxes = [bounds_of(tag) for tag in _NODE.findall(xml) if attribute(tag, "bounds")]
    return max(box[2] for box in boxes), max(box[3] for box in boxes)


def _matches(tag, selector):
    """A uiautomator2 selector (`d(resourceId=..., text=...)`), the keys the closers write."""
    for key, wanted in selector.items():
        value = {"resourceId": "resource-id", "resourceIdMatches": "resource-id", "text": "text",
                 "textContains": "text", "description": "content-desc",
                 "className": "class"}.get(key)
        if value is None:
            return False
        actual = attribute(tag, value)
        if key == "resourceIdMatches":
            if not re.fullmatch(wanted, actual):
                return False
        elif key == "textContains":
            if wanted not in actual:
                return False
        elif actual != wanted:
            return False
    return True


class _JsonRpc:
    def __init__(self, phone):
        self._phone = phone

    def swipePoints(self, flat, _steps):  # noqa: N802 -- uiautomator2's own name
        self._phone._gesture(("drag", list(zip(flat[::2], flat[1::2]))))


class SheetPhone:
    """Shows `screen`; each gesture shows the next screen of `after` (a capture, or a list).

    `closes_on` names the only kinds of gesture that change the screen (`("drag",)`: Back and taps
    leave the sheet where it is, as a focused comment field does with Back); by default, all do.
    """

    wait_timeout = 1.0

    def __init__(self, screen, after, closes_on=None):
        self.screen = screen
        self.after = [after] if isinstance(after, str) else list(after)
        self.closes_on = closes_on
        self.gestures = []
        self.width, self.height = screen_size(screen)
        self.info = {"displayWidth": self.width, "displayHeight": self.height}
        self.xpath = XPathEntry(self)
        self.jsonrpc = _JsonRpc(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "com.instagram.mainactivity.MainActivity"}

    def window_size(self):
        return self.width, self.height

    def _gesture(self, gesture):
        self.gestures.append(gesture)
        if self.closes_on is not None and gesture[0] not in self.closes_on:
            return
        self.screen = self.after.pop(0) if len(self.after) > 1 else self.after[0]

    def click(self, x, y):
        self._gesture(("click", int(x), int(y)))

    def press(self, key):
        self._gesture(("press", key))

    def swipe(self, *args, **_k):
        self._gesture(("swipe",) + tuple(int(v) for v in args[:4]))

    def __call__(self, **selector):
        phone = self
        tags = [tag for tag in _NODE.findall(self.screen) if _matches(tag, selector)]

        class _Element:
            def exists(self):
                return bool(tags)

            @property
            def info(self):
                left, top, right, bottom = bounds_of(tags[0])
                return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

            def click(self):
                phone.click(*centre_of(tags[0]))

        return _Element()


_DRAG_LINE = re.compile(r"^Gesture drag (?:down|up): \((\d+), (\d+)\) -> \((\d+), (\d+)\) in (\d+) ms$")


def drags_journaled(lines):
    """The drags of the gesture journal: ((start), (end), milliseconds) for each."""
    found = []
    for line in lines:
        match = _DRAG_LINE.match(line)
        if match:
            sx, sy, ex, ey, ms = (int(v) for v in match.groups())
            found.append(((sx, sy), (ex, ey), ms))
    return found


def assert_accompanied_drag(points, ms, screen_height, speed_band):
    """A finger that goes down, carries the sheet to the bottom of the screen and lifts at rest.

    - many points reported on the way, never a jump: the sheet is carried, not thrown;
    - at a hand's speed while it stays on the glass (`speed_band`, px/s), in 0.40-0.85 s, the
      long drag's own duration;
    - the last step a tenth of the largest at most: the finger lifts nearly still, so Android
      sees no fling and the sheet settles where the finger left it;
    - down to the bottom tenth of the screen.
    """
    steps = [b[1] - a[1] for a, b in zip(points, points[1:])]
    assert len(points) >= 20, points
    assert min(steps) >= 0, steps
    assert steps[-1] * 10 <= max(steps), steps
    assert points[-1][1] >= 0.9 * screen_height, points[-1]
    assert 400 <= ms <= 850, ms
    low, high = speed_band
    assert low <= (points[-1][1] - points[0][1]) / (ms / 1000) <= high, ms
