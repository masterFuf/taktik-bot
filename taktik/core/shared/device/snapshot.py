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
- stop on an invalid selector: `find`, `first` and `exists` log it and go on to the next one, as
  the production loops do behind `facade.xpath()` (which logs and returns None); `elements()`, the
  raw call, lets uiautomator2's error through.

Works with uiautomator2 3.x (`requirements.lock` pins 3.5.0): `XPathSelector(xpath).all(source)`
is the form common to 3.3 and 3.5+, whose constructor no longer takes a source.

Every selector asked of a photo is told to the observers of its source (`SnapshotSource.observe`,
`facade.observe_snapshots`): the Lab traces see a photo's questions as they saw `d.xpath()`'s.

The layer and its proof (`scripts/check_snapshot_equality.py`) are step 1. Step 2 wires it into
TikTok: its waiting probes take one photo per turn (`tiktok/actions/core/base_action.py`), and a
feed decision is read on one photo (`read_screen`, `tiktok/actions/atomic/detection/`). The
shared layer imports no platform module.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union

from loguru import logger
from lxml.etree import XPathError as LxmlXPathError, _Element as LxmlElement
from uiautomator2.xpath import PageSource, XMLElement, XPathError as U2XPathError, XPathSelector

from taktik.core.shared.device.ui_dump import parse_bounds

Selectors = Union[str, Sequence[str]]
# The namespaces uiautomator2 gives its own evaluation (`re:` is EXSLT regular expressions).
_XPATH_NAMESPACES = {"re": "http://exslt.org/regular-expressions"}
Rewrite = Optional[Callable[[str], str]]
# Told of every selector asked of a photo: (selector, found, elapsed_ms). The Lab traces wrap
# `device.xpath`, which a photo never calls: without this they would lose every selector.
Observer = Callable[[str, bool, float], None]


class SnapshotUnavailable(RuntimeError):
    """The screen could not be read: no dump, one that does not parse, or one with no node (what
    uiautomator2 returns after repeated empty hierarchies)."""


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
                 rewrite: Rewrite = None, observer: Optional[Observer] = None):
        if not xml_content:
            raise SnapshotUnavailable("empty dump")
        self._xml = xml_content
        self._source = PageSource(xml_content)
        try:
            root = self._source.root  # parse now: a dump that does not parse is not a photo
        except Exception as exc:
            raise SnapshotUnavailable(f"unparsable dump: {exc}") from exc
        if len(root) == 0:
            # `<hierarchy rotation="0" />`: no screen was read, which is not a screen without
            # the thing looked for.
            raise SnapshotUnavailable("empty hierarchy")
        self._taken_at = time.monotonic() if taken_at is None else taken_at
        self._rewrite = rewrite
        self._observer = observer
        self._cache: dict = {}

    @property
    def age_ms(self) -> float:
        """Since the dump was ASKED for: the screen may have moved while it was being taken."""
        return (time.monotonic() - self._taken_at) * 1000.0

    @property
    def source(self) -> PageSource:
        return self._source

    @property
    def xml(self) -> str:
        """The dump as the phone returned it, for whoever keeps screens (the screen ring)."""
        return self._xml

    @property
    def root(self):
        """The tree `d.xpath()` evaluates selectors against (tags are widget classes, `class` is
        gone), for a reader that walks it instead of asking selectors. The tree `parse_ui_dump`
        builds, node for node. Shared by every question asked of this photo: read it, never
        change it."""
        return self._source.root

    def elements_within(self, element, selector: str) -> list:
        """The elements a RELATIVE selector (`.//...`) finds under `element`, one of this photo's
        elements. `d.xpath()` has no relative form, so lxml evaluates it on the node; the
        device's rewrite still applies, so an id equality means here what it means in
        `elements()`. An invalid selector raises lxml's error."""
        started_at = time.perf_counter()
        found = []
        try:
            xpath = self._rewrite(selector) if self._rewrite else selector
            nodes = element.elem.xpath(xpath, namespaces=_XPATH_NAMESPACES)
            found = [XMLElement(node) for node in nodes if isinstance(node, LxmlElement)]
            return found
        finally:
            if self._observer is not None:
                self._tell(selector, bool(found), (time.perf_counter() - started_at) * 1000.0)

    def elements(self, selector: str) -> list:
        """The elements `d.xpath(selector).all()` finds on this screen, for READING: they carry no
        device, so they cannot be tapped. An invalid selector raises uiautomator2's error."""
        started_at = time.perf_counter()
        found = False
        try:
            if selector not in self._cache:
                xpath = self._rewrite(selector) if self._rewrite else selector
                self._cache[selector] = XPathSelector(xpath).all(self._source)
            found = bool(self._cache[selector])
            return self._cache[selector]
        finally:
            if self._observer is not None:
                self._tell(selector, found, (time.perf_counter() - started_at) * 1000.0)

    def _tell(self, selector: str, found: bool, elapsed_ms: float) -> None:
        try:
            self._observer(selector, found, elapsed_ms)
        except Exception as exc:  # an observer never changes an answer
            logger.debug(f"Screen photo observer failed on {selector!r}: {exc}")

    def _found_or_skipped(self, selector: str) -> list:
        try:
            return self.elements(selector)
        except (U2XPathError, LxmlXPathError) as exc:
            logger.warning(f"Invalid selector skipped on the screen photo: {selector!r} ({exc})")
            return []

    def find(self, selectors: Selectors) -> List[SnapshotNode]:
        for selector in _as_list(selectors):
            found = self._found_or_skipped(selector)
            if found:
                return [SnapshotNode.from_element(el) for el in found]
        return []

    def first(self, selectors: Selectors) -> Optional[SnapshotNode]:
        found = self.find(selectors)
        return found[0] if found else None

    def exists(self, selectors: Selectors) -> bool:
        return any(self._found_or_skipped(selector) for selector in _as_list(selectors))


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
        self._observers: List[Observer] = []

    def observe(self, observer: Observer) -> None:
        """Tell `observer` of every selector asked of the photos taken from now on."""
        with self._lock:
            self._observers.append(observer)

    def _tell_observers(self, selector: str, found: bool, elapsed_ms: float) -> None:
        for observer in list(self._observers):
            observer(selector, found, elapsed_ms)

    def photo_of(self, xml_content: Optional[str]) -> ScreenSnapshot:
        """A photo of a dump the caller already holds (read with its own timeout, or handed in):
        the same rewrite and observers as `snapshot()`, never kept for `max_age_s`."""
        return ScreenSnapshot(xml_content, rewrite=self._rewrite,
                              observer=self._tell_observers if self._observers else None)

    def snapshot(self, max_age_s: float = 0.0) -> ScreenSnapshot:
        with self._lock:
            last, generation = self._last, self._generation
        if max_age_s > 0 and last is not None and last.age_ms < max_age_s * 1000.0:
            return last
        asked_at = time.monotonic()
        photo = ScreenSnapshot(self._dump(), taken_at=asked_at, rewrite=self._rewrite,
                               observer=self._tell_observers if self._observers else None)
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
