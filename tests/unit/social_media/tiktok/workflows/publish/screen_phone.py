"""A phone for tests that shows real captured screens and moves between them as the phone did.

It answers what the publish code asks of a uiautomator2 device (`dump_hierarchy`, `xpath(...)`
with `wait`/`exists`/`click`, `click(x, y)`, `info`) from anonymized dumps under `fixtures/`, the
tree read by `parse_ui_dump` as `d.xpath()` reads it. Every tap is hit-tested like a finger: the
node that takes it is the last clickable node, in drawing order, whose bounds hold the point. The
next screen comes from `moves`, `(screen, resource-id after ":id/") -> screen`, written from the
gestures of a real session; a tap no move names leaves the screen as it was, and is recorded all
the same.
"""

from __future__ import annotations

from taktik.core.shared.device.ui_dump import center, dump_screen_size, parse_bounds, parse_ui_dump
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


class Tap:
    def __init__(self, x: int, y: int, screen: str, rid: str, bounds: str):
        self.x, self.y, self.screen, self.rid, self.bounds = x, y, screen, rid, bounds

    def __repr__(self) -> str:
        return f"Tap({self.x},{self.y} on {self.rid or '<no id>'} {self.bounds} of {self.screen})"


class _Selection:
    def __init__(self, phone: "ScreenPhone", xpath: str):
        self._phone = phone
        self._xpath = xpath

    def _nodes(self):
        return self._phone.tree().xpath(self._xpath)

    @property
    def exists(self) -> bool:
        return bool(self._nodes())

    def wait(self, timeout: float = 0.0) -> bool:
        return self.exists

    def click(self) -> None:
        nodes = self._nodes()
        if not nodes:
            raise RuntimeError(f"no node for {self._xpath}")
        self._phone.click(*center(parse_bounds(nodes[0].get("bounds"))))


class ScreenPhone:
    def __init__(self, screen: str, screens: dict[str, str], moves: dict[tuple[str, str], str]):
        self.screen = screen
        self._xml = {name: (FIXTURES / fixture).read_text(encoding="utf-8") for name, fixture in screens.items()}
        self._moves = moves
        self.taps: list[Tap] = []
        self.dumps = 0

    def tree(self):
        return parse_ui_dump(self._xml[self.screen])

    @property
    def info(self) -> dict:
        width, height = dump_screen_size(self.tree())
        return {"displayWidth": width, "displayHeight": height}

    def dump_hierarchy(self, compressed: bool = False) -> str:
        self.dumps += 1
        return self._xml[self.screen]

    def xpath(self, xpath: str) -> _Selection:
        return _Selection(self, xpath)

    def click(self, x: int, y: int) -> None:
        hit = None
        for node in self.tree().iter():
            bounds = parse_bounds(node.get("bounds") or "")
            if node.get("clickable") == "true" and bounds and bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]:
                hit = node  # document order is drawing order: the last one is on top
        rid = ((hit.get("resource-id") or "").split(":id/")[-1]) if hit is not None else ""
        self.taps.append(Tap(x, y, self.screen, rid, hit.get("bounds") if hit is not None else ""))
        self.screen = self._moves.get((self.screen, rid), self.screen)

    def tapped(self) -> list[str]:
        return [tap.rid for tap in self.taps]
