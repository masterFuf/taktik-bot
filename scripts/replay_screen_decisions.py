"""Replay the screen decisions of two states of the code on captured dumps. Read-only.

For each capture of a platform, under each version the overrides know (the baseline and every
version of `compat/data/overrides/<platform>.yaml`), in the language the capture shows, the
production reads run on a fake phone: its `xpath` is uiautomator2's own `XPathEntry` (the code
`d.xpath()` runs), its dump is the capture, its clock jumps when the code sleeps. Instagram's phone
is wrapped as every Instagram bridge wraps it (`CloneAwareDeviceProxy`, through the Lab's own
facade builder), so the replay sees the proxy's selector rewrite. The answers of the reads, and
the gestures they would make, are compared between a base revision (`git archive`) and the working
tree. Exit 1 on any difference.

TikTok (default): the popup scan, the comment sheet, the suggestion page, `get_video_info` as the
feed loops call it and in full, the For You and inbox checks, `is_user_followed`, the Lab's screen
name, and the top of a feed turn as the loop reads it (`feed_turn`). The dumps of a feed turn are
printed by kind of screen, with the fake cost of `--dump-ms` per dump.

Instagram (`--platform instagram`): the follow list readers (rows, usernames, the state of each
row's button, the tap on a row, the list checks), the unfollow's reads (its rows, tabs,
confirmation wait, row re-read), the profile checks it makes, the shared funnel
(`_is_element_present`, `_get_text_from_element`, `_wait_for_element`) asked every selector list of
the catalogues its callers read, and the readers that parse one dump themselves: the screen
signals and profile flags of `batch_xpath_check`, the profile texts, bio region and avatar crops,
and the tree the post-reading, feed, comment, suggestion, notification and persona readers walk.
The dumps of each read are printed by kind of screen, and per call for the reads made many times
on one screen. Each capture also carries, under `_why` in the report, every selector of those
one-dump readers that plain lxml on `parse_ui_dump` answers otherwise than the photo through the
proxy's rewrite, with the cause: the report explains an answer that changes.

    python scripts/replay_screen_decisions.py --corpus DIR [--corpus DIR ...] [--base HEAD]
    python scripts/replay_screen_decisions.py --platform instagram --list FILE [--save-list FILE]
        [--probes a,b] [--report FILE]

`--probes` replays only the named reads. The children keep the caller's PYTHONPATH after the code
of their state (another uiautomator2, for instance).

The corpus defaults to $TAKTIK_DEBUG_UI, else ./debug_ui (captures are personal data: never in
this repository). A read that exists in one state only is listed, not compared.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIKTOK_PACKAGES = ("com.zhiliaoapp.musically", "com.ss.android.ugc.trill", "com.ss.android.ugc.aweme",
                   "com.taktik.tt")
INSTAGRAM_PACKAGE = "com.instagram.android"
PROBES = ("popups", "comments", "suggestion", "video_info_feed", "video_info_full", "for_you",
          "inbox", "followed", "lab_screen", "feed_turn", "read_screen")
INSTAGRAM_PROBES = ("list_rows", "list_usernames", "row_states", "click_row", "list_open", "list_end",
                    "in_suggestions", "limited", "loading", "unfollow_rows", "tabs", "confirm_wait",
                    "row_unfollowed", "follow_back_row", "profile_screen", "profile_username",
                    "follow_button", "profile_check", "funnel_present", "funnel_text", "funnel_wait",
                    # Readers that parse one dump themselves (`batch_xpath_check` and the lxml
                    # readers of steps 3 L5-L6): answers, and the tree the walkers get.
                    "screen_signals", "profile_flags", "profile_text", "profile_enriched",
                    "bio_region", "avatar_header", "avatar_tab", "post_geometry", "feed_anchors",
                    "caption", "framed_post", "carousel", "reading_tree", "comments_tree",
                    "suggestions_tree", "suggestions_carousel", "discover_screen", "discover_rows",
                    "notifications_tree", "notifications_rows", "notifications_requests",
                    "persona_texts")
# Reads made many times on one screen (once per row, once per selector list): their dumps are
# also printed per call.
PER_CALL = ("row_states", "funnel_present", "funnel_text", "funnel_wait")
# The catalogues the shared funnel's Instagram callers read (`_is_element_present`,
# `_get_text_from_element`, `_wait_for_element`): every selector list of them is asked.
FUNNEL_CATALOGUES = ("DETECTION_SELECTORS", "PROFILE_SELECTORS", "BUTTON_SELECTORS", "POST_SELECTORS",
                     "STORY_SELECTORS", "UNFOLLOW_SELECTORS", "POPUP_SELECTORS", "FEED_SELECTORS",
                     "NAVIGATION_SELECTORS")
PLATFORMS = {
    "tiktok": {"packages": TIKTOK_PACKAGES, "probes": PROBES},
    "instagram": {"packages": ("com.instagram.",), "probes": INSTAGRAM_PROBES},
}


# ── Child: runs inside one state of the code (PYTHONPATH), never imports the other ─────────────

def _plain(value):
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def _language_module(platform: str):
    if platform == "instagram":
        from taktik.core.social_media.instagram.ui import language
    else:
        from taktik.core.social_media.tiktok.ui import language
    return language


def _child_languages(files, platform="tiktok"):
    from loguru import logger
    logger.remove()
    detection = _language_module(platform)._DETECTION

    class Screen:
        def __init__(self, xml):
            self.xml = xml

        def dump_hierarchy(self, *_a, **_k):
            return self.xml

    languages = {}
    for path in files:
        detection.reset()
        try:
            languages[path] = detection.detect_language(Screen(Path(path).read_text(encoding="utf-8", errors="replace")))
        except Exception:
            languages[path] = "unknown"
    return languages


def _fake_phone(dump_ms: float, package: str):
    """A phone whose clock jumps when the code sleeps or dumps, and which counts its dumps."""
    import time

    now = [1000.0]
    time.time = lambda: now[0]
    time.monotonic = lambda: now[0]
    time.sleep = lambda seconds: now.__setitem__(0, now[0] + max(float(seconds), 0.0))

    from uiautomator2.xpath import PageSource, XPathEntry

    # uiautomator2 parses every dump again, and the old code dumps once per selector: the parse of
    # a dump is kept for the next identical one, in both states. Queries only read the tree, so
    # the answers do not depend on it; the run time does (hours to minutes on the funnel probes).
    parse = PageSource.root.func
    parsed = {}

    def root(source):
        tree = parsed.get(source._xml_content)
        if tree is None:
            parsed.clear()
            tree = parsed[source._xml_content] = parse(source)
        return tree

    PageSource.root = property(root)

    class Phone:
        wait_timeout = 1.0

        def __init__(self):
            self.xml, self.dumps, self.gestures = "", 0, []
            self.xpath = XPathEntry(self)
            self.info = {"displayWidth": 1080, "displayHeight": 2400}
            # The bounded dump (`facade.get_xml_dump(timeout_seconds=...)`) goes through these.
            self.settings = {"max_depth": 50}
            phone = self

            class _JsonRpc:
                def dumpWindowHierarchy(self, *_a, **_k):
                    return phone.dump_hierarchy()

            self.jsonrpc = _JsonRpc()

        def dump_hierarchy(self, *_a, **_k):
            self.dumps += 1
            now[0] += dump_ms / 1000.0
            return self.xml

        def click(self, *args):
            self.gestures.append("click")

        def long_click(self, *args):
            self.gestures.append("long_click")

        def double_click(self, *args):
            self.gestures.append("double_click")

        def swipe(self, *args, **kwargs):
            self.gestures.append("swipe")

        def swipe_ext(self, *args, **kwargs):
            self.gestures.append("swipe")

        def press(self, key):
            self.gestures.append(f"press:{key}")

        def window_size(self):
            return 1080, 2400

        def app_current(self):
            return {"package": package, "activity": "unknown"}

    return Phone()


def _only(probes: dict, only) -> dict:
    return {name: probe for name, probe in probes.items() if name in only} if only else probes


def _child_decisions(files, version, language, dump_ms, only=None):
    from loguru import logger
    logger.remove()

    phone = _fake_phone(dump_ms, "com.zhiliaoapp.musically")

    from taktik.core.compat.selectors.setup import apply_version_overrides
    from taktik.core.social_media.tiktok.ui.language import detect_and_optimize

    apply_version_overrides("tiktok", version)
    phone.xml = Path(files[0]).read_text(encoding="utf-8", errors="replace")
    detect_and_optimize(phone, override=language if language in ("fr", "en") else None)

    from types import SimpleNamespace

    from bridges.compat.diagnostics.runtime.action_test.runner import _detect_screen
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import PopupHandler

    detection = DetectionActions(phone)
    handler = PopupHandler(None, detection)
    bundle = SimpleNamespace(detection=detection, device=detection.device)

    def feed_turn():
        """The top of a For You turn as the loop reads it: on one photo where the code reads
        the turn so (`read_screen`), else each read on its own."""
        if not callable(getattr(type(detection), "read_screen", None)):
            return {"popups": handler._fast_detect(), "comments": detection.has_comments_section_open(),
                    "suggestion": detection.has_suggestion_page(),
                    "video_info": detection.get_video_info(light_if_ad=True)}
        screen = detection.read_screen()
        return {"popups": handler.detect(screen), "comments": detection.has_comments_section_open(screen),
                "suggestion": detection.has_suggestion_page(screen),
                "video_info": detection.get_video_info(light_if_ad=True, screen=screen)}

    probes = {
        "popups": handler._fast_detect,
        "comments": detection.has_comments_section_open,
        "suggestion": detection.has_suggestion_page,
        "video_info_feed": lambda: detection.get_video_info(light_if_ad=True),
        "video_info_full": detection.get_video_info,
        "for_you": detection.is_on_for_you_page,
        "inbox": detection.is_on_inbox_page,
        "followed": detection.is_user_followed,
        "lab_screen": lambda: _detect_screen(bundle),
        "feed_turn": feed_turn,
    }
    if hasattr(detection, "read_screen"):
        probes["read_screen"] = lambda: getattr(detection.read_screen(), "kind", None)

    return _run_probes(files, phone, _only(probes, only))


def _run_probes(files, phone, probes, before_each=None):
    """Every probe on every capture: its answer, its gestures, its dumps, and how many calls it
    made when it reads many times on one screen (`calls`, set by the probe in `counted`)."""
    out = {}
    for path in files:
        phone.xml = Path(path).read_text(encoding="utf-8", errors="replace")
        if before_each is not None:
            before_each()
        answers = {}
        for name, probe in probes.items():
            dumps_before, gestures_before = phone.dumps, len(phone.gestures)
            counted = {}
            try:
                answer = _plain(probe(counted) if name in PER_CALL else probe())
            except Exception as exc:
                answer = f"error: {type(exc).__name__}"
            answers[name] = {"answer": answer, "gestures": phone.gestures[gestures_before:],
                             "dumps": phone.dumps - dumps_before}
            if "calls" in counted:
                answers[name]["calls"] = counted["calls"]
        out[path] = answers
    return out


def _funnel_selector_lists():
    """Every selector list of `FUNNEL_CATALOGUES` as the version and the language set it:
    (catalogue.field, selectors), a lone selector as a list of one."""
    import taktik.core.social_media.instagram.ui.selectors as catalogues

    lists = []
    for catalogue_name in FUNNEL_CATALOGUES:
        catalogue = getattr(catalogues, catalogue_name)
        for field in sorted(dir(catalogue)):
            if field.startswith("_"):
                continue
            try:
                value = getattr(catalogue, field)
            except Exception:
                continue
            if isinstance(value, str) and value:
                lists.append((f"{catalogue_name}.{field}", [value]))
            elif isinstance(value, (list, tuple)) and value and all(isinstance(s, str) for s in value):
                lists.append((f"{catalogue_name}.{field}", list(value)))
    return lists


def _child_instagram_decisions(files, version, language, dump_ms, only=None):
    from loguru import logger
    logger.remove()

    phone = _fake_phone(dump_ms, INSTAGRAM_PACKAGE)

    from taktik.core.compat.selectors.setup import apply_version_overrides
    from taktik.core.social_media.instagram.ui.language import detect_and_optimize

    apply_version_overrides("instagram", version)
    phone.xml = Path(files[0]).read_text(encoding="utf-8", errors="replace")
    detect_and_optimize(phone, override=language if language in ("fr", "en") else None)

    # The Lab's builder: the facade over `CloneAwareDeviceProxy`, as production mounts it.
    from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
        build_instagram_action_bundle, create_instagram_device_facade)
    from taktik.core.shared.diagnostics import run_halt

    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    detection, unfollow = bundle.detection, bundle.unfollow
    shown = {"names": [], "rows": []}

    def list_rows():
        rows = detection.get_visible_followers_with_elements()
        shown["names"] = [row["username"] for row in rows]
        return [(row["username"], tuple(row["element"].bounds)) for row in rows]

    def row_states(counted):
        counted["calls"] = len(shown["names"])
        return {name: detection.get_row_follow_state(name) for name in shown["names"]}

    def click_row():
        return detection.click_follower_in_list(shown["names"][0]) if shown["names"] else None

    def unfollow_rows():
        rows = unfollow._visible_follow_rows(with_display_names=True)
        shown["rows"] = [row["username"] for row in rows]
        return {"rows": [(row["username"], row["state"], row.get("display_name"), tuple(row["button"].bounds))
                         for row in rows],
                "suggestions": unfollow.suggestions_on_screen, "unpaired": unfollow.unpaired_on_screen}

    def tabs():
        return {kind: (unfollow._list_tab_selected(INSTAGRAM_PACKAGE, kind), unfollow._list_tab_count(kind))
                for kind in ("following", "followers")}

    def row_unfollowed():
        return unfollow._wait_row_unfollowed(shown["rows"][0]) if shown["rows"] else None

    def profile_check():
        """What the unfollow checks on a candidate's profile, for the profile shown."""
        username = detection.get_username_from_profile()
        if not username:
            return None
        return {"on_profile": unfollow._on_profile_of(username),
                "follows_you": unfollow._profile_follows_you(username),
                "verified": detection.is_verified_account(), "business": detection.is_business_account()}

    probes = {
        "list_rows": list_rows,
        "list_usernames": detection.extract_usernames_from_follow_list,
        "row_states": row_states,
        "click_row": click_row,
        "list_open": detection.is_followers_list_open,
        "list_end": detection.is_followers_list_end_reached,
        "in_suggestions": detection.is_in_suggestions_section,
        "limited": detection.is_followers_list_limited,
        "loading": detection.is_loading_spinner_visible,
        "unfollow_rows": unfollow_rows,
        "tabs": tabs,
        "confirm_wait": lambda: unfollow._tap_unfollow_confirm(timeout=unfollow.confirm_dialog_timeout),
        "row_unfollowed": row_unfollowed,
        "follow_back_row": unfollow._has_follow_back_row,
        "profile_screen": detection.is_on_profile_screen,
        "profile_username": detection.get_username_from_profile,
        "follow_button": unfollow.click_actions.get_follow_button_state,
        "profile_check": profile_check,
    }

    lists = _funnel_selector_lists()

    def funnel(read):
        def probe(counted):
            counted["calls"] = len(lists)
            return {name: read(selectors) for name, selectors in lists}
        return probe

    probes["funnel_present"] = funnel(detection._is_element_present)
    probes["funnel_text"] = funnel(detection._get_text_from_element)
    # One turn: the pause alone outlasts the timeout.
    probes["funnel_wait"] = funnel(lambda selectors: detection._wait_for_element(
        selectors, timeout=0.4, check_interval=0.5, silent=True))
    probes.update(_one_dump_reader_probes(bundle, phone))

    def before_each():
        # Each capture is a new screen: no signal of the previous one, no stop lock.
        for component in (detection, unfollow.detection_actions):
            component._screen_signal_snapshot_cache = None
        bundle.scroll._post_action_geometry_cache = None
        run_halt.reinitialiser()

    out = _run_probes(files, phone, _only(probes, only), before_each)
    rewrite = bundle.device._device.rewrite_xpath
    for path in files:
        out[path]["_why"] = _why_lxml_differs(Path(path).read_text(encoding="utf-8", errors="replace"),
                                              _one_dump_selector_lists(detection), rewrite)
    return out


class _Screenshot:
    """What an avatar crop needs of a screenshot: its size, and a crop that remembers its box."""

    size = (1080, 2400)

    def __init__(self, crops: list):
        self._crops = crops

    def crop(self, box):
        from PIL import Image

        self._crops.append(tuple(box))
        return Image.new("RGB", (max(1, box[2] - box[0]), max(1, box[3] - box[1])))


def _tree_digest(root):
    """Which tree a walker was handed: a digest of it, None for no tree."""
    import hashlib

    from lxml import etree

    return None if root is None else hashlib.sha1(etree.tostring(root)).hexdigest()[:16]


def _one_dump_reader_probes(bundle, phone) -> dict:
    """The Instagram readers that parse ONE dump themselves: `batch_xpath_check` (screen signals,
    profile flags) and the lxml readers, in both states by their production entry points."""
    from loguru import logger

    from bridges.instagram.analysis.runtime.persona_comments import PersonaCommentsMixin
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow)

    logger.remove()  # the bridge runtime the persona reader imports adds a debug sink on stderr

    detection, scroll, comment, feed = bundle.detection, bundle.scroll, bundle.comment, bundle.feed
    notifications = NotificationsEngagementWorkflow(bundle.device, "replay")
    persona = type("PersonaReader", (PersonaCommentsMixin,), {})()
    persona.device = bundle.device

    def cropped(extract):
        """The box an avatar extraction crops from the screenshot, None when it extracts nothing."""
        crops = []
        phone.screenshot = lambda *_a, **_k: _Screenshot(crops)
        try:
            result = extract()
        finally:
            del phone.screenshot
        return crops[-1] if result and crops else None

    def carousel():
        root = scroll._dump_root()
        found = scroll._current_framed_carousel(root) if root is not None else None
        return {"carousel": found, "reason": getattr(scroll, "_last_carousel_skip_reason", None)
                if root is not None else "hierarchy_unavailable"}

    def post_geometry():
        scroll._post_action_geometry_cache = None
        return scroll._read_post_action_geometry()

    return {
        "screen_signals": detection._get_screen_signal_snapshot,
        "profile_flags": detection.get_profile_flags_batch,
        "profile_text": detection.get_profile_text_batch,
        "profile_enriched": detection.get_enriched_profile_data,
        "bio_region": detection._truncated_bio_region,
        "avatar_header": lambda: cropped(detection.extract_profile_image),
        "avatar_tab": lambda: cropped(detection.extract_own_avatar_from_tab),
        "post_geometry": post_geometry,
        "feed_anchors": scroll._read_feed_anchors,
        "caption": scroll.current_caption_text,
        "framed_post": scroll.framed_post_context,
        "carousel": carousel,
        "reading_tree": lambda: _tree_digest(scroll._dump_root()),
        "comments_tree": lambda: _tree_digest(comment._dump_comments_root()),
        "suggestions_tree": lambda: _tree_digest(feed._suggestions_dump_root()),
        "suggestions_carousel": feed.detect_feed_suggestions_carousel,
        "discover_screen": feed.is_on_discover_people_screen,
        "discover_rows": feed.scan_discover_suggestions,
        "notifications_tree": lambda: _tree_digest(notifications._dump_root()),
        "notifications_rows": notifications._dump_screen,
        "notifications_requests": notifications._request_rows,
        "persona_texts": persona._visible_comment_texts,
    }


def _one_dump_selector_lists(detection) -> list:
    """(reader.field, selectors) of every list the one-dump readers ask, as the version and the
    language set them. The banner title is relative to a banner row: asked of the whole screen."""
    from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS as ps

    ds, sel = detection.detection_selectors, detection.selectors
    return [
        ("signals.home", ds.home_screen_indicators), ("signals.search", ds.search_screen_indicators),
        ("signals.profile_surface", ds.profile_surface_indicators),
        ("signals.profile", ds.profile_screen_indicators),
        ("signals.story_viewer", ds.story_viewer_indicators), ("signals.post", ds.post_screen_indicators),
        ("flags.is_private", ds.private_account_indicators),
        ("flags.is_verified", ds.verified_account_indicators),
        ("flags.is_business", ds.business_account_indicators),
        ("text.username", sel.username), ("text.full_name", sel.full_name), ("text.bio", sel.bio),
        ("enriched.username", ps.enrichment_username_selectors),
        ("enriched.full_name", ps.enrichment_full_name_selectors),
        ("enriched.category", ps.enrichment_category_selectors),
        ("enriched.bio", ps.enrichment_bio_selectors), ("enriched.website", ps.enrichment_website_selectors),
        ("enriched.banner", ps.enrichment_banner_selectors),
        ("enriched.banner_title", [ps.enrichment_banner_title_selector.lstrip(".")]),
        ("avatar.header", ps.profile_picture_imageview), ("avatar.tab", ps.tab_profile_avatar),
    ]


def _why_lxml_differs(xml: str, lists: list, rewrite) -> dict:
    """For one capture: each selector of `lists` that plain lxml on `parse_ui_dump` (what the
    one-dump readers asked) answers otherwise than the photo through the proxy's rewrite (what
    they ask now), with the cause: `rewrite` when the photo without the rewrite agrees with lxml,
    else `engine` (uiautomator2's own evaluation). `gained`/`lost`: resource-ids of the nodes
    the photo adds or drops."""
    from taktik.core.shared.device.snapshot import ScreenSnapshot
    from taktik.core.shared.device.ui_dump import parse_ui_dump

    tree = parse_ui_dump(xml)
    try:
        plain, photo = ScreenSnapshot(xml), ScreenSnapshot(xml, rewrite=rewrite)
    except Exception as exc:
        return {"unreadable": type(exc).__name__}

    def by_lxml(selector):
        try:
            found = tree.xpath(selector)
        except Exception:
            return None
        return [n.getroottree().getpath(n) if hasattr(n, "getroottree") else repr(n) for n in found] \
            if isinstance(found, list) else [repr(found)] if found else []

    def by_photo(snapshot, selector):
        try:
            return [el.elem.getroottree().getpath(el.elem) for el in snapshot.elements(selector)]
        except Exception:
            return None

    def ids(paths):
        root = plain.source.root  # `root` is new in the working tree: the base has `source` only
        out = []
        for path in paths or []:
            nodes = root.getroottree().xpath(path) if path.startswith("/") else []
            out.append(nodes[0].get("resource-id", "") if nodes else path)
        return sorted(set(out))[:6]

    found = {}
    for name, selectors in lists:
        for selector in selectors or []:
            old, new = by_lxml(selector), by_photo(photo, selector)
            # A reader skips a selector its engine rejects: rejected finds nothing.
            if (old or []) == (new or []):
                continue
            cause = "rewrite" if (by_photo(plain, selector) or []) == (old or []) else "engine"
            gained = [p for p in (new or []) if p not in (old or [])]
            lost = [p for p in (old or []) if p not in (new or [])]
            found.setdefault(name, []).append({
                "selector": selector, "lxml": "rejected" if old is None else len(old),
                "photo": "rejected" if new is None else len(new), "cause": cause,
                "gained": ids(gained), "lost": ids(lost)})
    return found


def child_main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", required=True, choices=("languages", "decisions"))
    parser.add_argument("--files", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--platform", default="tiktok", choices=tuple(PLATFORMS))
    parser.add_argument("--version", default="")
    parser.add_argument("--language", default="unknown")
    parser.add_argument("--dump-ms", type=float, default=250.0)
    parser.add_argument("--probes", default="")
    args = parser.parse_args(argv)
    only = [name for name in args.probes.split(",") if name]
    files = [line for line in Path(args.files).read_text(encoding="utf-8").splitlines() if line]
    if args.child == "languages":
        result = _child_languages(files, args.platform)
    elif args.platform == "instagram":
        result = _child_instagram_decisions(files, args.version, args.language, args.dump_ms, only)
    else:
        result = _child_decisions(files, args.version, args.language, args.dump_ms, only)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


# ── Parent ─────────────────────────────────────────────────────────────────────

def _run_child(code_root: Path, workdir: Path, tag: str, files, **options) -> dict:
    list_file = workdir / f"{tag}.files"
    out_file = workdir / f"{tag}.json"
    list_file.write_text("\n".join(files), encoding="utf-8")
    command = [sys.executable, str(Path(__file__).resolve()), "--files", str(list_file), "--out", str(out_file)]
    for key, value in options.items():
        command += [f"--{key.replace('_', '-')}", str(value)]
    kept = os.environ.get("PYTHONPATH")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(code_root) + (os.pathsep + kept if kept else "")}
    done = subprocess.run(command, cwd=str(code_root), env=env, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"{tag} failed:\n{done.stderr[-2000:]}")
    return json.loads(out_file.read_text(encoding="utf-8"))


def _extract(revision: str, workdir: Path) -> Path:
    archive = subprocess.run(["git", "archive", "--format=tar", revision, "taktik", "bridges"],
                             cwd=ROOT, check=True, capture_output=True).stdout
    target = workdir / "base"
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target)
    return target


def _versions(platform: str = "tiktok") -> list:
    import yaml

    data = yaml.safe_load((ROOT / f"taktik/core/compat/data/overrides/{platform}.yaml").read_text(encoding="utf-8")) or {}
    baseline = str((data.get("meta") or {}).get("baseline_version")
                   or {"tiktok": "43.1.4", "instagram": "410.0.0.53.71"}[platform])
    return [baseline] + [str(v) for v in (data.get("versions") or {}) if str(v) != baseline]


def _dumps(args) -> list:
    if args.list:
        listed = [line.strip() for line in Path(args.list).read_text(encoding="utf-8").splitlines() if line.strip()]
        return listed[:: max(1, args.every)]
    packages = PLATFORMS[args.platform]["packages"]
    corpora = args.corpus or [os.environ.get("TAKTIK_DEBUG_UI") or str(ROOT / "debug_ui")]
    found = []
    for corpus in corpora:
        base = Path(corpus)
        for path in sorted(base.rglob("*.xml")) if base.is_dir() else []:
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(f'package="{package}' in text for package in packages):
                found.append(str(path))
    return found[:: max(1, args.every)]


def _decide(root: Path, workdir: Path, label: str, groups: dict, dump_ms: float, jobs: int,
            platform: str = "tiktok", only=()) -> dict:
    tasks = []
    for (version, language), files in groups.items():
        for index in range(0, len(files), 60):
            tag = f"{label}-{version}-{language}-{index}"
            tasks.append((tag, version, language, files[index:index + 60]))

    def run(task):
        tag, version, language, files = task
        answers = _run_child(root, workdir, tag, files, child="decisions", platform=platform,
                             version=version, language=language, dump_ms=dump_ms,
                             probes=",".join(only))
        return {(path, version): value for path, value in answers.items()}

    merged = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for part in pool.map(run, tasks):
            merged.update(part)
    return merged


FEED_TURN = ("popups", "comments", "suggestion", "video_info_feed")


def _turn_dumps(answers: dict) -> int:
    """The dumps of the top of a feed turn as the loop reads it (`feed_turn`), else the sum of
    its reads taken one by one."""
    if "feed_turn" in answers:
        return answers["feed_turn"]["dumps"]
    return sum(answers[p]["dumps"] for p in FEED_TURN if p in answers)


def screen_kind(answers: dict) -> str:
    """What the base's reads say the capture is, to break the dumps down."""
    def said(probe):
        return (answers.get(probe) or {}).get("answer")

    if "list_rows" in answers or "profile_screen" in answers:
        unfollow_rows = said("unfollow_rows")
        for kind, present in (("list", bool(said("list_rows")) or bool((unfollow_rows or {}).get("rows")
                                                                         if isinstance(unfollow_rows, dict) else False)),
                              ("dialog", said("confirm_wait") is True),
                              ("profile", said("profile_screen") is True)):
            if present:
                return kind
        return "other"

    info = said("video_info_feed")
    info = info if isinstance(info, dict) else {}
    for kind, present in (("comments", said("comments") is True), ("suggestion", said("suggestion") is True),
                          ("inbox", said("inbox") is True), ("live", info.get("is_live")),
                          ("ad", info.get("is_ad")), ("video", info.get("author"))):
        if present:
            return kind
    return "unknown"


def _differing(old: dict, new: dict) -> tuple:
    """The two sides of a difference; dict answers (one entry per call) narrowed to the keys that
    differ, so a long answer shows where it changed."""
    old_answer, new_answer = old["answer"], new["answer"]
    if isinstance(old_answer, dict) and isinstance(new_answer, dict):
        keys = [k for k in sorted(set(old_answer) | set(new_answer)) if old_answer.get(k) != new_answer.get(k)]
        old = {**old, "answer": {k: old_answer.get(k) for k in keys}}
        new = {**new, "answer": {k: new_answer.get(k) for k in keys}}
    return old, new


def compare(before: dict, after: dict, probes=PROBES) -> dict:
    """Answers and gestures of each read, base against now, per (capture, version).

    A read present in one state only is listed, not compared; a capture missing from `after`
    counts as a difference for each of its reads. `per_probe[probe][kind]` keeps the dumps of each
    read, base and now, by kind of screen, and the calls of the reads made many times on one
    screen. An example whose answers are both dicts keeps only the keys that differ."""
    compared = differences = 0
    examples, only_one_side = [], set()
    dumps_before, dumps_after = [], []
    by_kind: dict = {}
    per_probe: dict = {}
    for key in sorted(before):
        old, new = before[key], after.get(key)
        if new is None:
            differences += len(old)
            examples.append((Path(key[0]).name, key[1], "(missing)", {"answer": None, "gestures": []},
                             {"answer": "missing now", "gestures": []}))
            continue
        kind = screen_kind(old)
        for probe in probes:
            if (probe in old) != (probe in new):
                only_one_side.add(probe)
                continue
            if probe not in old:
                continue
            compared += 1
            if (old[probe]["answer"], old[probe]["gestures"]) != (new[probe]["answer"], new[probe]["gestures"]):
                differences += 1
                if len(examples) < 20:
                    examples.append((Path(key[0]).name, key[1], probe, *_differing(old[probe], new[probe])))
            cell = per_probe.setdefault(probe, {}).setdefault(kind, {"before": [], "after": [], "calls": 0,
                                                                     "sum_before": 0, "sum_after": 0})
            cell["before"].append(old[probe]["dumps"])
            cell["after"].append(new[probe]["dumps"])
            calls = old[probe].get("calls")
            if calls:
                cell["calls"] += calls
                cell["sum_before"] += old[probe]["dumps"]
                cell["sum_after"] += new[probe]["dumps"]
        dumps_before.append(_turn_dumps(old))
        dumps_after.append(_turn_dumps(new))
        pair = by_kind.setdefault(kind, ([], []))
        pair[0].append(dumps_before[-1])
        pair[1].append(dumps_after[-1])
    return {"compared": compared, "differences": differences, "examples": examples,
            "only_one_side": sorted(only_one_side), "dumps_before": dumps_before or [0],
            "dumps_after": dumps_after or [0], "by_kind": by_kind, "per_probe": per_probe}


def _print_tiktok(outcome: dict, dump_ms: float) -> None:
    dumps_before, dumps_after = outcome["dumps_before"], outcome["dumps_after"]
    print(f"Dumps of a feed turn as the loop reads it (popups, comments, suggestion, video info) at "
          f"{dump_ms:.0f} ms each: base median {statistics.median(dumps_before):.0f} "
          f"(max {max(dumps_before)}), now median {statistics.median(dumps_after):.0f} (max {max(dumps_after)}).")
    for kind, (old_dumps, new_dumps) in sorted(outcome["by_kind"].items()):
        print(f"  {kind:10} {len(old_dumps):4} decisions: base median {statistics.median(old_dumps):.0f} "
              f"(max {max(old_dumps)}), now median {statistics.median(new_dumps):.0f} (max {max(new_dumps)})")


def _print_per_probe(outcome: dict, probes) -> None:
    """Dumps of each read by kind of screen, base -> now: median (max), and per call for the
    reads made many times on one screen."""
    print("Dumps per read, by kind of screen, base -> now: median (max)"
          + "; per call for " + ", ".join(PER_CALL))
    for probe in probes:
        cells = outcome["per_probe"].get(probe) or {}
        parts = []
        for kind, cell in sorted(cells.items()):
            text = (f"{kind} {len(cell['before'])}: {statistics.median(cell['before']):.0f} ({max(cell['before'])})"
                    f" -> {statistics.median(cell['after']):.0f} ({max(cell['after'])})")
            if cell["calls"]:
                text += (f", per call {cell['sum_before'] / cell['calls']:.2f} -> "
                         f"{cell['sum_after'] / cell['calls']:.2f} ({cell['calls']} calls)")
            parts.append(text)
        print(f"  {probe:17} " + " | ".join(parts))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--child" in argv:
        return child_main(argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--platform", default="tiktok", choices=tuple(PLATFORMS))
    parser.add_argument("--corpus", action="append", help="a capture folder (repeatable)")
    parser.add_argument("--list", help="read the captures from this file, one path per line")
    parser.add_argument("--save-list", help="write the captures replayed to this file")
    parser.add_argument("--every", type=int, default=1, help="one capture in K (sampling)")
    parser.add_argument("--base", default="HEAD", help="revision to compare the working tree with")
    parser.add_argument("--dump-ms", type=float, default=250.0, help="fake cost of one dump")
    parser.add_argument("--report", help="write every answer of both states to this JSON file")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--probes", default="", help="replay only these reads (comma-separated)")
    args = parser.parse_args(argv)
    platform = args.platform
    only = [name for name in args.probes.split(",") if name]
    probes = [p for p in PLATFORMS[platform]["probes"] if not only or p in only]

    dumps = _dumps(args)
    if not dumps:
        print(f"No {platform} capture found: nothing to replay.")
        return 0
    if args.save_list:
        Path(args.save_list).write_text("\n".join(dumps) + "\n", encoding="utf-8")
    versions = _versions(platform)

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        languages = _run_child(ROOT, workdir, "languages", dumps, child="languages", platform=platform)
        groups = {}
        for path in dumps:
            for version in versions:
                groups.setdefault((version, languages.get(path, "unknown")), []).append(path)
        base_root = _extract(args.base, workdir)
        before = _decide(base_root, workdir, "base", groups, args.dump_ms, args.jobs, platform, only)
        after = _decide(ROOT, workdir, "now", groups, args.dump_ms, args.jobs, platform, only)

    outcome = compare(before, after, probes)
    counts = {language: sum(1 for v in languages.values() if v == language) for language in set(languages.values())}
    print(f"{len(dumps)} {platform} captures (languages {counts}) x versions {versions}; base {args.base}.")
    print(f"Decisions compared: {outcome['compared']}, differences: {outcome['differences']}.")
    if outcome["only_one_side"]:
        print(f"Reads present in one state only (not compared): {outcome['only_one_side']}")
    if platform == "tiktok":
        _print_tiktok(outcome, args.dump_ms)
    else:
        _print_per_probe(outcome, probes)
    for name, version, probe, old, new in outcome["examples"]:
        print(f"  DIFF {name} {version} {probe}: {json.dumps(old['answer'], ensure_ascii=False)[:160]} "
              f"{old['gestures']} -> {json.dumps(new['answer'], ensure_ascii=False)[:160]} {new['gestures']}")
    if args.report:
        report = {f"{path} @ {version}": {"base": before[(path, version)], "now": after.get((path, version))}
                  for path, version in sorted(before)}
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if outcome["differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
