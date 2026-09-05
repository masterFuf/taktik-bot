"""One-pass perception of the currently visible TikTok video surface.

The feed used to ask uiautomator2 one XPath question at a time.  On the Galaxy A11 every
question can trigger another accessibility hierarchy read, so a handful of one-second lookups
turn into a 25-35 second gap.  This parser keeps the hierarchy as the unit of observation.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from lxml import etree

from taktik.core.shared.device.ui_dump import parse_bounds


Bounds = Tuple[int, int, int, int]


@dataclass(frozen=True)
class VideoSnapshot:
    # True means the hierarchy was read and parsed successfully. This is independent from
    # video_visible: a profile is a valid negative observation, not a reason to retry every
    # legacy video selector.
    hierarchy_parsed: bool = False
    author: Optional[str] = None
    description: Optional[str] = None
    sound: Optional[str] = None
    like_count: Optional[str] = None
    signature: Optional[str] = None
    interactive_bounds: List[Bounds] = field(default_factory=list)
    is_liked: bool = False
    is_favorited: bool = False
    is_ad: bool = False
    video_visible: bool = False


_AUTHOR_IDS = {"title", "ej6"}
_AVATAR_IDS = {"yx4", "user_avatar"}
_DESCRIPTION_IDS = {"desc"}
_LIKE_COUNT_IDS = {"f4z", "g2j"}
_VIDEO_IDS = {"gy_", "long_press_layout"}


def _short_id(node) -> str:
    return (node.get("resource-id") or "").rsplit("/", 1)[-1]


def _first_text(nodes, ids) -> Optional[str]:
    for node in nodes:
        if _short_id(node) in ids:
            value = (node.get("text") or "").strip()
            if value:
                return value
    return None


def _author_from_avatar(nodes) -> Optional[str]:
    for node in nodes:
        if _short_id(node) not in _AVATAR_IDS:
            continue
        desc = (node.get("content-desc") or "").strip()
        for prefix, suffix in (("Profile ", ""), ("Profil ", ""), ("", " profile")):
            if prefix and desc.startswith(prefix):
                return desc[len(prefix):].strip() or None
            if suffix and desc.lower().endswith(suffix):
                return desc[:-len(suffix)].strip() or None
    return None


def _like_count(nodes) -> Optional[str]:
    value = _first_text(nodes, _LIKE_COUNT_IDS)
    if value:
        return value
    for node in nodes:
        desc = (node.get("content-desc") or "").strip()
        match = re.search(r"(?:Like|Unlike) video[.\s]+(.+?)\s+likes?\b", desc, re.I)
        if match:
            return match.group(1).strip()
        if any(word in desc for word in ("Attribuer", "Retirer", "Supprimer")):
            match = re.search(r"([0-9][0-9\s.,KkMm]*)\s+(?:«\s*)?J['’]aime", desc)
            if match:
                return match.group(1).strip()
    return None


def _sound(nodes) -> Optional[str]:
    for node in nodes:
        desc = (node.get("content-desc") or "").strip()
        match = re.match(r"(?:Sound|Son)\s*:\s*(.+)", desc, re.I)
        if match:
            return match.group(1).strip()
    return None


def _interactive_bounds(nodes) -> List[Bounds]:
    parsed = [parse_bounds(node.get("bounds") or "") for node in nodes]
    valid = [bounds for bounds in parsed if bounds]
    if not valid:
        return []
    screen_w = max(bounds[2] for bounds in valid)
    screen_h = max(bounds[3] for bounds in valid)
    result: List[Bounds] = []
    for node, bounds in zip(nodes, parsed):
        if bounds is None:
            continue
        interactive = node.get("clickable") == "true" or (node.get("class") or node.tag).endswith("Button")
        if not interactive:
            continue
        left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        # Full-screen video/pager containers are the intended swipe surface.  Small full-width
        # header rows remain protected; only large two-dimensional overlays are discarded.
        if width >= 0.80 * screen_w and height >= 0.22 * screen_h:
            continue
        if bounds not in result:
            result.append(bounds)
    return result


def parse_video_snapshot(xml: str) -> VideoSnapshot:
    if not xml:
        return VideoSnapshot()
    try:
        root = etree.fromstring(xml.encode("utf-8"))
    except (ValueError, etree.XMLSyntaxError):
        return VideoSnapshot()

    nodes = list(root.iter())
    author = _first_text(nodes, _AUTHOR_IDS) or _author_from_avatar(nodes)
    description = _first_text(nodes, _DESCRIPTION_IDS)
    like_count = _like_count(nodes)
    sound = _sound(nodes)
    video_visible = any(
        _short_id(node) in _VIDEO_IDS
        or (node.get("content-desc") or "") in {"Video", "Vidéo"}
        for node in nodes
    )
    identity = "\x1f".join(value for value in (author, description, sound) if value)
    if not identity and author:
        identity = "\x1f".join(value for value in (author, like_count) if value)
    signature = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20] if identity else None

    liked = any(
        (_short_id(node) in {"f4u", "g2c", "f57", "g2w"}
         and (node.get("selected") == "true" or node.get("checked") == "true"))
        or "unlike" in (node.get("content-desc") or "").lower()
        or ("retirer" in (node.get("content-desc") or "").lower()
            and "aime" in (node.get("content-desc") or "").lower())
        for node in nodes
    )
    favorited = any(
        (_short_id(node) == "gtn" and node.get("selected") == "true")
        or "remove from favourite" in (node.get("content-desc") or "").lower()
        or "retirer des favoris" in (node.get("content-desc") or "").lower()
        for node in nodes
    )
    ad = any((node.get("text") or "").strip().lower() in {"ad", "sponsorise", "sponsorisé", "publicite", "publicité"}
             for node in nodes)

    return VideoSnapshot(
        hierarchy_parsed=True,
        author=author,
        description=description,
        sound=sound,
        like_count=like_count,
        signature=signature,
        interactive_bounds=_interactive_bounds(nodes) if video_visible else [],
        is_liked=liked,
        is_favorited=favorited,
        is_ad=ad,
        video_visible=video_visible,
    )
