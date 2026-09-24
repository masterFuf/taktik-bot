"""One photo of the screen answers every question about it (step 1 of the one-photo spec).

Every `d.xpath(selector).exists` makes uiautomator2 dump the whole screen again; a screen probed
with ten selectors is ten dumps (M1 measured 170 to 260 ms each on a Pixel 6a). A `ScreenSnapshot`
is ONE dump on which any number of selectors are evaluated locally.

Exact by construction, not by imitation: each selector goes through uiautomator2's own
`XPathSelector(...).all()` on the photo's `PageSource` -- the code `d.xpath(selector).all()` runs
after its own dump, shorthand translation (`strict_xpath`), tag renaming and `re:` namespace
included, whatever version is installed. The one step before it is the device's: every Instagram
bridge mounts `CloneAwareDeviceProxy`, whose `xpath()` rewrites each `@resource-id="pkg:id/X"`
equality so it also matches a clone's prefix and the bare ids of Instagram's Compose screens. A
photo taken through a device that rewrites (`rewrite_xpath`) applies the same rewrite.

What a photo does NOT do, deliberately:
- serve an old screen: `SnapshotSource.snapshot()` takes a new photo each time; reusing one
  (`max_age_s`) is for a caller that knows no gesture happened since;
- turn a failed dump into an empty screen: it raises `SnapshotUnavailable`, where `d.xpath()`
  would have raised too; `wait_for` keeps trying until its timeout;
- hide an invalid selector: uiautomator2's error goes through, as under `d.xpath()`.

Step 1 only: the layer and its proof (`scripts/check_snapshot_equality.py`); it is wired into no
workflow. The shared layer imports no platform module.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union

from uiautomator2.xpath import PageSource, XPathSelector

from taktik.core.shared.device.ui_dump import parse_bounds

Selectors = Union[str, Sequence[str]]
Rewrite = Optional[Callable[[str], str]]


class SnapshotUnavailable(RuntimeError):
    """The screen could not be read: no dump, or one that does not parse."""


@dataclass(frozen=True)
class SnapshotNode:
    """One element of the photo, with what the bot reads and taps."""

    text: str
    content_desc: str
    resource_id: str
    package: str
    class_name: str
    bounds: Optional[Tuple[int, int, int, int]]
    clickable: bool
    enabled: bool
    selected: bool
    checked: bool
    focused: bool
    scrollable: bool

    @classmethod
    def from_element(cls, element) -> "SnapshotNode":
        """`element`: what uiautomator2's `.all()` returns (its `XMLElement`)."""
        node = element.elem
        attrib = node.attrib

        def flag(name: str) -> bool:
            return attrib.get(name) == "true"

        return cls(
            text=attrib.get("text", ""),
            content_desc=attrib.get("content-desc", ""),
            resource_id=attrib.get("resource-id", ""),
            package=attrib.get("package", ""),
            class_name=node.tag,
            bounds=parse_bounds(attrib.get("bounds", "")),
            clickable=flag("clickable"),
            enabled=flag("enabled"),
            selected=flag("selected"),
            checked=flag("checked"),
            focused=flag("focused"),
            scrollable=flag("scrollable"),
        )


class ScreenSnapshot:
    """A dump, parsed once. Selectors: one string or a list, the first that finds anything wins."""

    def __init__(self, xml_content: Optional[str], taken_at: Optional[float] = None,
                 rewrite: Rewrite = None):
        if not xml_content:
            raise SnapshotUnavailable("empty dump")
        self._source = PageSource(xml_content)
        try:
            self._source.root  # parse now: a dump that does not parse is not a photo
        except Exception as exc:
            raise SnapshotUnavailable(f"unparsable dump: {exc}") from exc
        self._taken_at = time.monotonic() if taken_at is None else taken_at
        self._rewrite = rewrite
        self._cache: dict = {}

    @property
    def age_ms(self) -> float:
        """Since the dump was ASKED for: the screen may have moved while it was being taken."""
        return (time.monotonic() - self._taken_at) * 1000.0

    @property
    def source(self) -> PageSource:
        return self._source

    def elements(self, selector: str) -> list:
        """What `d.xpath(selector).all()` would return on this screen (uiautomator2 elements)."""
        if selector not in self._cache:
            xpath = self._rewrite(selector) if self._rewrite else selector
            self._cache[selector] = XPathSelector(xpath, source=self._source).all()
        return self._cache[selector]

    def find(self, selectors: Selectors) -> List[SnapshotNode]:
        for selector in _as_list(selectors):
            found = self.elements(selector)
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
    """Takes photos from a dump function.

    `dump`: returns the screen's XML (the facade's `get_xml_dump`). `rewrite`: the device's
    selector rewrite, when it has one. A new photo each time, unless the caller accepts one no
    older than `max_age_s` AND nothing invalidated it since; `invalidate()` is what every gesture
    will call once they all go through the facade (later steps of the spec). A photo whose dump
    was asked before an invalidation is never kept.
    """

    def __init__(self, dump: Callable[[], Optional[str]], rewrite: Rewrite = None):
        self._dump = dump
        self._rewrite = rewrite
        self._lock = threading.Lock()
        self._last: Optional[ScreenSnapshot] = None
        self._generation = 0

    def snapshot(self, max_age_s: float = 0.0) -> ScreenSnapshot:
        with self._lock:
            last, generation = self._last, self._generation
        if max_age_s > 0 and last is not None and last.age_ms < max_age_s * 1000.0:
            return last
        asked_at = time.monotonic()
        photo = ScreenSnapshot(self._dump(), taken_at=asked_at, rewrite=self._rewrite)
        with self._lock:
            if self._generation == generation:
                self._last = photo
        return photo

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._last = None

    def wait_for(self, predicate: Callable[[ScreenSnapshot], bool], timeout: float,
                 poll_ms: int = 300) -> Optional[ScreenSnapshot]:
        """New photos at a fixed pace until `predicate` holds: the photo, or None at the timeout.
        One photo answers for every selector at once, instead of one wait per selector. A dump
        that fails is not an answer: the wait goes on."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                photo = self.snapshot()
            except SnapshotUnavailable:
                photo = None
            if photo is not None and predicate(photo):
                return photo
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_ms / 1000.0)


__all__ = ["ScreenSnapshot", "SnapshotNode", "SnapshotSource", "SnapshotUnavailable"]
