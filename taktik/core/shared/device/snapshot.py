"""One photo of the screen answers every question about it (step 1 of the one-photo spec).

Every `d.xpath(selector).exists` makes uiautomator2 dump the whole screen again; a screen probed
with ten selectors is ten dumps (M1 measured 170 to 260 ms each on a Pixel 6a). A `ScreenSnapshot`
is ONE dump, parsed once as `d.xpath()` sees it (`parse_ui_dump`: the tag is the widget class), on
which any number of selectors are evaluated locally, exactly as uiautomator2 would (its
`strict_xpath` shorthand translation included).

Step 1 only: the layer and its proof. It is wired into no workflow; the proof is strict equality
with uiautomator2's own XPath engine for every selector of the catalogue on the captured dumps
(`scripts/check_snapshot_equality.py`, `tests/unit/shared/device/test_snapshot.py`). The shared
layer imports no platform module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union

from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump

Selectors = Union[str, Sequence[str]]

# uiautomator2 evaluates its xpaths with this namespace (the `re:` functions).
_NAMESPACES = {"re": "http://exslt.org/regular-expressions"}


def _to_xpath(selector: str) -> str:
    """The selector as uiautomator2's `d.xpath()` evaluates it (shorthands translated)."""
    from uiautomator2.xpath import strict_xpath

    return strict_xpath(selector)


@dataclass(frozen=True)
class SnapshotNode:
    """One element of the photo, with what the bot reads and taps."""

    text: str
    content_desc: str
    resource_id: str
    class_name: str
    bounds: Optional[Tuple[int, int, int, int]]
    clickable: bool
    enabled: bool
    selected: bool
    checked: bool

    @classmethod
    def from_element(cls, element) -> "SnapshotNode":
        attrib = element.attrib

        def flag(name: str) -> bool:
            return attrib.get(name) == "true"

        return cls(
            text=attrib.get("text", ""),
            content_desc=attrib.get("content-desc", ""),
            resource_id=attrib.get("resource-id", ""),
            class_name=element.tag,
            bounds=parse_bounds(attrib.get("bounds", "")),
            clickable=flag("clickable"),
            enabled=flag("enabled"),
            selected=flag("selected"),
            checked=flag("checked"),
        )


class ScreenSnapshot:
    """A parsed dump. Selectors: one string or a list, the first that finds anything wins."""

    def __init__(self, xml_content: Optional[str], taken_at: Optional[float] = None):
        self._root = parse_ui_dump(xml_content) if xml_content else None
        self._taken_at = time.monotonic() if taken_at is None else taken_at
        self._cache: dict = {}

    @property
    def age_ms(self) -> float:
        return (time.monotonic() - self._taken_at) * 1000.0

    @property
    def is_empty(self) -> bool:
        return self._root is None

    def elements(self, selector: str) -> list:
        """The raw lxml elements a selector finds (the same ones uiautomator2 would find)."""
        if self._root is None:
            return []
        if selector not in self._cache:
            # An invalid selector finds nothing here (uiautomator2 raises on it: the checker
            # leaves those out of the comparison).
            try:
                self._cache[selector] = self._root.xpath(_to_xpath(selector), namespaces=_NAMESPACES)
            except Exception:
                self._cache[selector] = []
        found = self._cache[selector]
        return found if isinstance(found, list) else []

    def find(self, selectors: Selectors) -> List[SnapshotNode]:
        for selector in _as_list(selectors):
            found = [el for el in self.elements(selector) if hasattr(el, "attrib")]
            if found:
                return [SnapshotNode.from_element(el) for el in found]
        return []

    def first(self, selectors: Selectors) -> Optional[SnapshotNode]:
        found = self.find(selectors)
        return found[0] if found else None

    def exists(self, selectors: Selectors) -> bool:
        return any(self.elements(selector) for selector in _as_list(selectors))


def _as_list(selectors: Selectors) -> Iterable[str]:
    return [selectors] if isinstance(selectors, str) else list(selectors)


class SnapshotSource:
    """Takes photos from a dump function, keeps the last one for `ttl_s`, until a gesture.

    `dump`: returns the screen's XML (the facade's `get_xml_dump`). `invalidate()` is what every
    gesture will call once they all go through the facade (later steps of the spec).
    """

    def __init__(self, dump: Callable[[], Optional[str]], ttl_s: float = 0.25):
        self._dump = dump
        self._ttl_s = ttl_s
        self._last: Optional[ScreenSnapshot] = None

    def snapshot(self, fresh: bool = False) -> ScreenSnapshot:
        if not fresh and self._last is not None and self._last.age_ms < self._ttl_s * 1000.0:
            return self._last
        self._last = ScreenSnapshot(self._dump())
        return self._last

    def invalidate(self) -> None:
        self._last = None

    def wait_for(self, predicate: Callable[[ScreenSnapshot], bool], timeout: float,
                 poll_ms: int = 300) -> Optional[ScreenSnapshot]:
        """New photos at a fixed pace until `predicate` holds: the photo, or None at the timeout.
        One photo answers for every selector at once, instead of one wait per selector."""
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snapshot(fresh=True)
            if predicate(snap):
                return snap
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_ms / 1000.0)


__all__ = ["ScreenSnapshot", "SnapshotNode", "SnapshotSource"]
