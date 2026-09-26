"""What the TikTok screen shows, read on ONE photo (step 2 of the one-photo spec).

A feed decision used to ask its questions one at a time, each probe dumping the screen once per
selector and waiting out its own timeout to prove an absence: 37 dumps on a video, 16 on an ad,
50 on a LIVE preview. `read_screen()` takes one photo (a new one every 0.3 s until the screen is
recognised, 2 s at most) and answers all of them on it.

The signals are the production readers themselves, handed the photo (`screen=`): no selector is
written here. Asked without a photo, a reader still waits for its own target as before ("am I
there yet?" is not "what is this screen?"). A photo serves ONE decision and is never cached: the
workflow holds several facades, and a gesture made through one does not invalidate another's
photo, so whoever makes a gesture reads again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, Optional, Set, Tuple

from taktik.core.shared.device.ui_dump import parse_bounds

SYSTEM_UI_PACKAGE = 'com.android.systemui'
SCREEN_WAIT_S = 2.0
SCREEN_POLL_MS = 300

# First that holds names the screen: a popup covers what is under it, a sheet or a suggestion
# page interrupts the feed, then the surfaces, then what the feed shows.
KINDS = ("popup", "comments", "suggestion", "profile", "inbox", "live", "ad", "video")


@dataclass(frozen=True)
class TikTokScreen:
    """One photo and what it shows. `photo` is None when no dump could be read: then every reader
    handed this screen finds nothing."""

    photo: object = None
    popups: FrozenSet[str] = frozenset()
    overlay_region: Optional[Tuple[int, int, int, int]] = None
    comments: bool = False
    suggestion: bool = False
    profile: bool = False
    inbox: bool = False
    for_you: bool = False
    live: bool = False
    ad: bool = False
    video: bool = False

    @property
    def kind(self) -> str:
        """The inbox is a surface, not a popup, even though the popup handler escapes it."""
        present = {"popup": bool(self.popups - {"inbox_page"}), "comments": self.comments,
                   "suggestion": self.suggestion, "profile": self.profile, "inbox": self.inbox,
                   "live": self.live, "ad": self.ad, "video": self.video}
        return next((kind for kind in KINDS if present[kind]), "unknown")

    @property
    def recognised(self) -> bool:
        return self.kind != "unknown"

    @property
    def photo_age_ms(self) -> Optional[float]:
        return None if self.photo is None else self.photo.age_ms

    def signals(self) -> Dict[str, object]:
        return {"popups": sorted(self.popups), "comments": self.comments,
                "suggestion": self.suggestion, "profile": self.profile, "inbox": self.inbox,
                "for_you": self.for_you, "live": self.live, "ad": self.ad, "video": self.video}


def read_until(device, read: Callable, done: Callable, timeout: float = SCREEN_WAIT_S):
    """`read(photo)` on a new photo every 0.3 s until `done(reading)` holds or `timeout` ends: the
    last reading either way, None when no photo could be taken."""
    last = []

    def settled(photo) -> bool:
        last[:] = [read(photo)]
        return done(last[0])

    device.wait_for_snapshot(settled, timeout, poll_ms=SCREEN_POLL_MS)
    return last[0] if last else None


def popup_families(present: Callable) -> Set[str]:
    """The popup families on a screen, named as the popup handler handles them. `present(selectors)`
    says whether one of them is on the screen: the handler's own dump scan and the photo share
    this one table."""
    from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
    from ....ui.selectors.shell.popups import POPUP_SELECTORS
    from ....ui.selectors.surfaces.inbox import INBOX_SELECTORS

    table = (
        ('system_deny', (POPUP_SELECTORS.system_deny_button,)),
        ('system_input', (POPUP_SELECTORS.system_input_method_popup,)),
        ('system_dialog', (POPUP_SELECTORS.system_dialog,)),
        ('notification_banner', (POPUP_SELECTORS.notification_banner,)),
        ('inbox_page', (INBOX_SELECTORS.inbox_title, NAVIGATION_SELECTORS.inbox_tab_selected)),
        ('link_email', (POPUP_SELECTORS.link_email_popup,)),
        ('gdpr', (POPUP_SELECTORS.gdpr_popup,)),
        ('follow_friends', (POPUP_SELECTORS.follow_friends_popup,)),
        ('collections', (POPUP_SELECTORS.collections_popup,)),
        ('generic_popup', (POPUP_SELECTORS.close_button, POPUP_SELECTORS.dismiss_button)),
        ('video_options_sheet', (POPUP_SELECTORS.video_options_sheet,)),
    )
    return {family for family, fields in table if any(present(selectors) for selectors in fields)}


def action_block_evidence(tree) -> Optional[str]:
    """The phrase by which TikTok refuses the account's actions on this screen, or None.

    Read on the dump tree (`parse_ui_dump`), so the popup handler asks it of the photo it already
    took. A phrase inside what people wrote (caption, comment, message, bio) proves nothing.
    """
    from ....ui.selectors.shell.screen_state import DETECTION_SELECTORS

    if tree is None:
        return None

    def nodes(selectors):
        found = []
        for xpath in selectors:
            try:
                found.extend(tree.xpath(xpath))
            except Exception:  # noqa: BLE001 - a selector this tree cannot read proves nothing
                continue
        return found

    written = set(nodes(DETECTION_SELECTORS.user_written_text))
    for node in nodes(DETECTION_SELECTORS.rate_limit):
        if node in written or any(ancestor in written for ancestor in node.iterancestors()):
            continue
        return (node.get('text') or '').strip()[:120] or None
    return None


def note_action_block(tree) -> bool:
    """Is TikTok refusing actions on this screen? Seeing it sets the run's stop latch."""
    evidence = action_block_evidence(tree)
    if not evidence:
        return False
    from taktik.core.shared.diagnostics import run_halt

    run_halt.demander_arret(run_halt.ACTION_BLOCKED, f"tiktok ({evidence})", evidence=evidence)
    return True


def unlabelled_overlay_region(tree):
    """The frame of an app dialog that exposes no readable node, or None.

    The "update the app" prompt of TikTok 43.1.4 is drawn without a single text or content-desc:
    no selector can see it, Back does not close it, and every tap of the run lands on the dim
    layer behind it. Its signature is structural: the app's nodes are there, none carries a
    label, and the largest frame inside the screen has a dialog's shape: at least a fifth of the
    screen, centred, clear of the top and bottom edges. A loading screen (a logo on an empty page)
    does not qualify.
    """
    app_nodes = [node for node in tree.iter()
                 if node.get('package') and node.get('package') != SYSTEM_UI_PACKAGE]
    if not app_nodes:
        return None
    if any((node.get('text') or '').strip() or (node.get('content-desc') or '').strip()
           for node in app_nodes):
        return None
    boxes = [parse_bounds(node.get('bounds') or '') for node in app_nodes]
    boxes = [box for box in boxes if box and box[2] > box[0] and box[3] > box[1]]
    if not boxes:
        return None
    def area(box):
        return (box[2] - box[0]) * (box[3] - box[1])

    screen = max(boxes, key=area)
    inner = [box for box in boxes if box != screen]
    if not inner:
        return None
    frame = max(inner, key=area)
    width, height = screen[2] - screen[0], screen[3] - screen[1]
    centred = abs((frame[0] - screen[0]) - (screen[2] - frame[2])) <= 0.05 * width
    clear_of_edges = frame[1] - screen[1] > 0.05 * height and screen[3] - frame[3] > 0.05 * height
    if area(frame) < 0.2 * area(screen) or not centred or not clear_of_edges:
        return None
    return frame


class ScreenReading:
    """`read_screen()` for `DetectionActions`: its readers, asked of one photo."""

    def read_screen(self, until: Optional[Callable[[TikTokScreen], bool]] = None,
                    timeout: float = SCREEN_WAIT_S) -> TikTokScreen:
        """The screen, read on one photo. New photos every 0.3 s until one satisfies `until`
        (default: recognised, any kind but `unknown`), `timeout` at most; the last photo read
        either way."""
        done = until or (lambda screen: screen.recognised)
        return read_until(self.device, self.screen_of, done, timeout) or TikTokScreen()

    def screen_of(self, photo) -> TikTokScreen:
        """What `photo` shows, by the production readers asked of it."""
        from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

        popups = popup_families(lambda selectors: self._element_exists(selectors, screen=photo))
        if note_action_block(getattr(getattr(photo, 'source', None), 'root', None)):
            popups.add('action_blocked')
        overlay = None
        if not popups:
            overlay = unlabelled_overlay_region(photo.source.root)
            if overlay is not None:
                popups.add('unlabelled_overlay')
        comments = self.has_comments_section_open(screen=photo)
        suggestion = self.has_suggestion_page(screen=photo)
        profile = self._element_exists(PROFILE_SELECTORS.profile_page_indicator, screen=photo)
        inbox = self.is_on_inbox_page(screen=photo)
        for_you = self.is_on_for_you_page(screen=photo)
        video, ad, live = self.feed_item_on(photo)
        return TikTokScreen(photo=photo, popups=frozenset(popups), overlay_region=overlay,
                            comments=comments, suggestion=suggestion, profile=profile, inbox=inbox,
                            for_you=for_you, live=live, ad=ad, video=video)


__all__ = ["KINDS", "SCREEN_WAIT_S", "ScreenReading", "TikTokScreen", "popup_families",
           "read_until", "unlabelled_overlay_region"]
