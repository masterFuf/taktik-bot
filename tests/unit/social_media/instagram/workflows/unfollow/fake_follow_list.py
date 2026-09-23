"""A follow list rendered as uiautomator XML, and a fake device that answers xpath from it.

Synthetic on purpose: the dumps captured on real phones carry real usernames and never enter
this public repository. The structure (resource ids, button texts, content-desc) follows the
dumps of Instagram 410 and 447 in English and French captured in September 2026; the usernames
are invented.
"""

from typing import Iterable, List, Optional, Tuple

from lxml import etree

PKG = "com.instagram.android"
ROW_HEIGHT = 180
TOP = 600


def follow_list_xml(rows: Iterable[Tuple[Optional[str], str]], extra: str = "") -> str:
    """rows = [(username or None, button text)]; `extra` is appended inside the hierarchy."""
    nodes = []
    for index, (username, button_text) in enumerate(rows):
        top = TOP + index * ROW_HEIGHT
        if username is not None:
            nodes.append(
                f'<node index="0" text="{username}" resource-id="{PKG}:id/follow_list_username" '
                f'class="android.widget.TextView" content-desc="" bounds="[200,{top + 40}][700,{top + 90}]" />'
            )
        nodes.append(
            f'<node index="1" text="{button_text}" resource-id="{PKG}:id/follow_list_row_large_follow_button" '
            f'class="android.widget.TextView" content-desc="" bounds="[760,{top + 30}][1040,{top + 150}]" />'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
        + "".join(nodes) + extra + "</node></hierarchy>"
    )


class FakeElement:
    def __init__(self, node):
        self._node = node
        self.clicked = 0

    @property
    def text(self) -> str:
        return self._node.get("text", "")

    @property
    def attrib(self):
        return dict(self._node.attrib)

    @property
    def bounds(self):
        raw = self._node.get("bounds", "[0,0][0,0]")
        left_top, right_bottom = raw[1:-1].split("][")
        left, top = (int(v) for v in left_top.split(","))
        right, bottom = (int(v) for v in right_bottom.split(","))
        return left, top, right, bottom

    def click(self):
        self.clicked += 1


class FakeSelector:
    def __init__(self, screen: "FakeScreen", xpath: str):
        self._screen = screen
        self._xpath = xpath

    def all(self) -> List[FakeElement]:
        return [FakeElement(node) for node in self._screen.tree().xpath(self._xpath)]

    @property
    def exists(self) -> bool:
        return bool(self._screen.tree().xpath(self._xpath))

    def click(self):
        self._screen.clicks.append(self._xpath)

    @property
    def bounds(self):
        found = self.all()
        return found[0].bounds if found else None


class FakeScreen:
    """Stands for the raw uiautomator2 device: `xpath()` reads the current XML.

    `screens` is a list of XML strings; `advance()` moves to the next one (the screen after a
    tap), so a test can script what Instagram shows before and after an action.
    """

    def __init__(self, *screens: str):
        self.screens = list(screens)
        self.index = 0
        self.clicks: List[str] = []

    def tree(self):
        return etree.fromstring(self.screens[self.index].encode("utf-8"))

    def xpath(self, xpath: str) -> FakeSelector:
        return FakeSelector(self, xpath)

    def advance(self):
        if self.index < len(self.screens) - 1:
            self.index += 1


class FakeFacade:
    """The device facade a business action holds: `.device` is the raw device."""

    def __init__(self, screen: FakeScreen):
        self.device = screen
        self.taps: List[tuple] = []

    def human_tap(self, bounds, quick=False):
        self.taps.append(tuple(bounds))
        self.device.advance()
        return True
