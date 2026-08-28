"""Naming a screen by its SHAPE, so we can tell two of them apart.

A run says an action stopped working. It never says what was on screen, and the Lab's baseline
is filed by (platform, language, device) — no version, and nothing at all that describes the
screen. So two different screens land in the same cell and a regression reads as an unexplained
flip.

That gap has a measured cost. Instagram serves story layout VARIANTS from its servers: two phones
on the same app version can be shown different screens, and a validated function breaks with no
version number moving. A key built on version numbers cannot express that, ever.

This names a screen by the shape of its view tree, which is the thing that actually changed.

WHAT IS IN THE HASH, and why each choice:

- `class`, because it is the one attribute obfuscation does not reach. Measured over the 17
  TikTok dumps of the parity survey: 1 495 of 1 529 nodes carry an `android.*` / `androidx.*`
  framework class; only 34 occurrences across 4 distinct app classes are obfuscated (`X.122f`).
- the resource-id ENTRY, package stripped, because `com.zhiliaoapp.musically:id/desc` and
  `…musically.go:id/desc` are the same screen on two clones of the same app.
- the depth, because a flat multiset of ids cannot tell a row moved from a row rewritten.

WHAT IS NOT, and why:

- `text` and `content-desc`. They change with every video, every username, every counter — a
  fingerprint including them would differ on every capture, which is the same as having none.
  They are also localised, so the same screen on a French phone would not match an English one.
- `bounds`. One extra row shifts every coordinate below it. Geometry is recorded beside the
  fingerprint as a soft signal (`screen_density`), never inside it.

WHAT IT CANNOT SEE: a change that does not touch the tree — a colour, an icon, a label. An equal
fingerprint says the STRUCTURE is unchanged, never that the screen is identical. That is why a
screenshot is kept next to it, and why this must not be presented as proof of identity.

WHY THERE ARE TWO LEVELS, and not one. The exact hash above was the whole design until it was run
against the 17 real dumps, where two captures of the SAME For You feed came out different. The
cause was not list length: real screens carry transient chrome. Between two captures of 46.6.3
For You, a banner left the top of the tree (`pcw`/`pct`/`pcx`) and a coach mark arrived deep in it
(`wb_guide`, `v_touch_area`, `tv_upvote`). Both are the same screen to anyone looking at it.

So identity is carried by the SET of resource-ids, and the exact hash demoted to a secondary
signal. Measured over every pair of the 17 dumps, Jaccard on that set:

    same screen, same version      0.94 - 0.99
    different screens, same ver.   0.12 - 0.42     <- a wide, clean gap
    same screen, ACROSS versions   0.09 - 0.33     <- as different as a different screen

The third line is the one to remember: a TikTok version bump makes a screen unrecognisable by its
ids, because only ~1% of obfuscated ids survive a build. Nothing here bridges two versions, and
nothing should pretend to — that is the readable-id and structure question, not this one.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

# `com.zhiliaoapp.musically:id/desc` -> `desc`. A resource-id with no `/` is kept whole rather
# than dropped: it is malformed, and silently ignoring it would make two different trees hash
# the same.
_RESOURCE_ID = re.compile(r"^[^/]*/(.*)$")

FINGERPRINT_VERSION = "1"
"""Bumped whenever the hashed shape changes, and carried in the digest.

Without it, a stored fingerprint from an older definition compares equal-or-not against a new one
with no way to know the rule itself moved — which would read as "they changed the screen".
"""


def _entry_of(resource_id: str) -> str:
    if not resource_id:
        return ""
    match = _RESOURCE_ID.match(resource_id)
    return match.group(1) if match else resource_id


def _walk(node: ET.Element, depth: int, out: list) -> None:
    """Depth-first, in document order — the order uiautomator emits, so it is reproducible."""
    attrs = node.attrib
    # uiautomator2 renames `<node class="X">` to `<X>`, so the tag IS the class once it has been
    # through the device; a raw AOSP dump keeps `<node class=…>`. Accept both, or a fingerprint
    # taken from a stored file would never match one taken live.
    klass = attrs.get("class") or (node.tag if node.tag != "node" else "")
    out.append(f"{depth}|{klass}|{_entry_of(attrs.get('resource-id', ''))}")
    for child in node:
        _walk(child, depth + 1, out)


def _root_of(xml_source: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(xml_source)
    except ET.ParseError:
        return None


def layout_fingerprint(xml_source: str) -> Optional[str]:
    """A stable digest of the screen's structure, or None if the dump does not parse.

    None rather than a sentinel string: an unparseable dump has no shape, and a caller that
    stored `'unparseable'` as if it were a layout would file every broken capture together.
    """
    root = _root_of(xml_source)
    if root is None:
        return None
    lines: list = []
    _walk(root, 0, lines)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]
    return f"v{FINGERPRINT_VERSION}:{digest}"


def screen_density(xml_source: str) -> Dict[str, Any]:
    """Counts that live BESIDE the fingerprint, never inside it.

    Two captures with the same fingerprint but a very different node or text count describe a
    screen that filled up or emptied — which is how an empty list is told apart from a broken
    one. Putting them in the hash instead would make every scroll a new layout.
    """
    root = _root_of(xml_source)
    if root is None:
        return {"nodes": 0, "clickable": 0, "with_text": 0, "with_desc": 0, "parsed": False}

    nodes = clickable = with_text = with_desc = 0
    for node in root.iter():
        attrs = node.attrib
        if "class" not in attrs and "resource-id" not in attrs and node.tag == "hierarchy":
            continue
        nodes += 1
        if attrs.get("clickable") == "true":
            clickable += 1
        if attrs.get("text", "").strip():
            with_text += 1
        if attrs.get("content-desc", "").strip():
            with_desc += 1

    return {
        "nodes": nodes,
        "clickable": clickable,
        "with_text": with_text,
        "with_desc": with_desc,
        "parsed": True,
    }


def screen_skeleton(xml_source: str) -> Optional[list]:
    """The sorted set of resource-id entries on screen — the screen's IDENTITY.

    Returned as a list rather than a hash, and stored that way: what an operator needs when a
    surface changes is not "the digest moved", it is WHICH ids appeared and which left. On the
    46.6.3 For You feed that difference reads directly as `+wb_guide +tv_upvote / -pcw -pct`,
    i.e. a coach mark arrived and a banner went — a sentence, instead of two hex strings.

    None when the dump does not parse, for the same reason as `layout_fingerprint`.
    """
    root = _root_of(xml_source)
    if root is None:
        return None
    entries = set()
    for node in root.iter():
        entry = _entry_of(node.attrib.get("resource-id", ""))
        if entry:
            entries.add(entry)
    return sorted(entries)


def skeleton_similarity(left: Optional[list], right: Optional[list]) -> float:
    """Jaccard between two skeletons. 1.0 when both are empty, 0.0 when either is unparseable.

    NOT a threshold — deliberately. Measured on the 17 survey dumps the gap is wide (same screen
    0.94+, other screen 0.42-), but three same-screen pairs is not enough evidence to freeze a
    cutoff in shared code. The caller decides, and says where its number came from.
    """
    if left is None or right is None:
        return 0.0
    a, b = set(left), set(right)
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


__all__ = [
    "layout_fingerprint",
    "screen_skeleton",
    "skeleton_similarity",
    "screen_density",
    "FINGERPRINT_VERSION",
]
