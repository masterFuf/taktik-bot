"""A screen test reads a real screen, never one written by hand.

Rule of the anti-drift doctrine ("Tester ce qui touche l'ecran"): what reads or
touches the screen is proven on a phone first, and the captures of that proof, anonymized, become
the regression test. A screen written by hand tests the code against what its author imagined.

A test screen therefore lives in a `fixtures/` folder as a real uiautomator dump, anonymized by
`scripts/anonymize_dump.py`. This gate is red when:

- a test file (`tests/**/*.py`) writes screen markup (`<node`, `<hierarchy`, `<android.widget.X`,
  docstrings aside) and is named in none of the three lists below;
- a listed file writes more markup than its ceiling (one per string literal that carries some);
- a listed file writes less than its ceiling, or none: lower the ceiling, or drop the entry
  (the lists only shrink);
- the list of hand-written screens holds more, or fewer, entries than `HAND_WRITTEN_CEILING`;
- an `.xml` under `tests/` sits outside a `fixtures/` folder, or does not have the shape of a
  uiautomator dump (a `hierarchy` root with its `rotation`, every node with the attributes the
  device writes): a hand-written fixture.

The three lists, one entry per file, each with its ceiling and why it holds:

- `HAND_WRITTEN` (a): a screen written by hand that a screen reading is tested on. Forbidden for
  new tests; each entry names the capture that removes it.
- `MINIMAL_TREES` (b): a tree that is not a screen, for pure logic (an engine, a counter, a
  digest, a guard). Tolerated when the reason says what is computed.
- `DUMP_EXCERPTS` (c): an excerpt copied from a real dump (ids, nesting and bounds of the
  capture), written inline before fixtures were the rule. A new one goes to `fixtures/`.

Blind spot, said: a test can still fake a screen without markup (an object answering `.info` or
`.exists` by hand); the gate does not see it.

    python scripts/audit_screen_test_fixtures.py              # green / red
    python scripts/audit_screen_test_fixtures.py --inventory  # every file with markup, and its list
    python scripts/audit_screen_test_fixtures.py --self-test  # the gate turns red on each fake
"""

from __future__ import annotations

import ast
import re
import sys
from functools import lru_cache
from pathlib import Path

from lxml import etree

CORE = Path(__file__).resolve().parents[1]
TESTS = CORE / "tests"

MARKUP = re.compile(r"<(?:node|hierarchy)[\s>/]|<android\.[\w.$]+[\s>/]")
DUMP_ATTRIBUTES = (
    "index", "text", "resource-id", "class", "package", "content-desc", "checkable", "checked",
    "clickable", "enabled", "focusable", "focused", "scrollable", "long-clickable", "password",
    "selected", "bounds",
)

#: (a) A screen written by hand that a screen reading is tested on. Each reason names what to
#: capture instead. Converted files leave the list; nothing enters it.
HAND_WRITTEN: dict[str, tuple[int, str]] = {
    "tests/unit/agent/test_autopilot_block_stop.py":
        (1,
         "Instagram's Try again later dialog, invented: none in the corpus, and it only shows once "
         "Instagram refuses a gesture. The ordinary screen is a real feed."),
    "tests/unit/social_media/instagram/test_action_blocked_stops_the_run.py":
        (8,
         "the rate-limit dialog and the contacts request, invented: neither is in the corpus; "
         "capture both (410, French)."),
    "tests/unit/social_media/instagram/test_profile_header_447.py":
        (9,
         "447 and 410 profile headers in the real shapes: no 447 professional profile in the "
         "corpus; capture one (447, French). 447 personal and 410 headers are in the corpus."),
    "tests/unit/social_media/instagram/test_verified_and_business_signals.py":
        (7,
         "two verified signals no capture shows: a profile title whose description carries the "
         "word Verified, and a certified card in the suggestions of a profile. A certified 410 FR "
         "profile (Pixel 4a) shows neither: its title's description is the handle, and the "
         "certified accounts of its suggestions carry no mark. Every other case reads a real "
         "profile (410 FR and EN, 447 FR)."),
    "tests/unit/social_media/instagram/ui/test_unfollow_selector_catalogs.py":
        (2,
         "the private account's unfollow confirmation, invented: it only shows once a followed "
         "account's button is tapped, which is the unfollow itself; tabs, categories and the sort "
         "button read real lists (447 FR, 410 EN and FR)."),
    "tests/unit/social_media/instagram/workflows/management/test_notifications_dump_parsing.py":
        (2,
         "the follow-requests screen (with and without its row containers), invented: the Pixel 4a "
         "account is public and the 3a shows the entry but no capture opened it; capture it on a "
         "private account with a pending request (410, French). The activity rows are real (410 "
         "FR and EN)."),
    "tests/unit/social_media/instagram/workflows/management/test_notifications_suggestions_parsing.py":
        (14,
         "the suggestions zone at the bottom of the activity screen, rebuilt by helpers from an "
         "old capture: no capture reaches it (Pixel 4a, 410 FR: 220 scrolls without it); capture "
         "it on an account with few notifications. The list above it is real."),
    "tests/unit/social_media/instagram/workflows/test_like_comment_in_thread.py":
        (1,
         "a comment WE already liked and a like control with an unknown label, written by hand: "
         "capture a comments sheet after a like (410, French and English); the like lands on a "
         "real sheet."),
    "tests/unit/social_media/instagram/workflows/unfollow/fake_follow_list.py":
        (17,
         "follow lists of 410 and 447 rendered by a helper for the engine's scripted runs: the 410 "
         "lists are in fixtures/ (ig410_*_followers_list*); no unfollow dialog in the corpus: "
         "capture it (410, French) and a 447 list."),
    "tests/unit/social_media/instagram/workflows/unfollow/test_unfollow_list_proof.py":
        (1, "one extra follow-list row, invented."),
    "tests/unit/social_media/instagram/workflows/unfollow/test_unfollow_list_rows.py":
        (2,
         "unfollow dialog and rows, invented: capture the unfollow dialog (410, French); rows are "
         "in fixtures/."),
    "tests/unit/social_media/instagram/workflows/unfollow/test_unfollow_verification.py":
        (2,
         "unfollow dialog and rows, invented: capture the unfollow dialog (410, French); rows are "
         "in fixtures/."),
    "tests/unit/social_media/tiktok/actions/test_screen_reading.py":
        (1,
         "TikTok's GDPR notice, invented: it shows once and no capture holds it. Every other "
         "screen is a real capture (43.1.4 and 46.9.3)."),
    "tests/unit/social_media/tiktok/actions/test_tiktok_dm_send_confirmation.py":
        (6, "DM conversation and composer, invented."),
    "tests/unit/social_media/tiktok/actions/test_tiktok_dm_sends_the_asked_text.py":
        (4, "DM composer, invented."),
    "tests/unit/social_media/tiktok/actions/test_tiktok_notification_banner.py":
        (6, "real comment sheet fixture, plus the message banner rebuilt by a helper."),
    "tests/unit/social_media/tiktok/actions/test_tiktok_notification_handles.py":
        (34, "Activity rows (suggestion, wave) invented in the 43.1.4 shape."),
    "tests/unit/social_media/tiktok/ui/test_tiktok_comment_sheet_label_route.py":
        (6,
         "the 46.6.3 sheets (full, empty, with typed text) rebuilt by a helper after their "
         "captures: no phone runs 46.6.3, and typing is a gesture. The 43.1.4 sheets (full, "
         "empty), the 43.1.4 and 47.0.3 video pages and the 47.0.3 sheet are real."),
    "tests/unit/social_media/tiktok/ui/test_tiktok_dm_anchors.py":
        (4, "conversation and inbox rows, invented in the captured shapes."),
    "tests/unit/social_media/tiktok/workflows/publish/test_tiktok_publish_hashtag_suggestions.py":
        (3,
         "hashtag suggestion list, invented: not in the publish runs of the corpus; capture it "
         "while typing a caption (43.1.4, French)."),
    "tests/unit/social_media/tiktok/workflows/publish/test_tiktok_publish_screen_detector.py":
        (6,
         "publish screens as markers: gallery, camera and post screens are in the publish runs "
         "(43.1.4); the one video editor captured is English and is not detected (French markers "
         "only): capture the French editor."),
    "tests/unit/social_media/tiktok/workflows/publish/test_tiktok_publish_selectors.py":
        (5,
         "publish screen markers, invented: the post screen is in the publish runs (43.1.4); "
         "capture the French video editor."),
    "tests/unit/social_media/tiktok/workflows/publish/test_tiktok_publish_upload_picker.py":
        (3,
         "upload picker: the button is in the publish runs (43.1.4); no hidden, disabled or tiny "
         "candidate in the corpus: capture the picker while it loads."),
    "tests/unit/social_media/tiktok/workflows/test_tiktok_block_stop.py":
        (4,
         "TikTok refusal toasts and dialogs, invented: none in the corpus; capture one (43.1.4, "
         "French)."),
    "tests/unit/social_media/tiktok/workflows/unfollow/conftest.py":
        (4, "following list of 46.6.3 rendered by a helper."),
    "tests/unit/test_switch_account.py":
        (4,
         "account rows by a helper: a sheet of several accounts with the notifications suffix, and "
         "the logged-out picker (no phone of the bench holds several accounts; the picker needs a "
         "log out). The one-account sheet, the own profile and the home feed are real (410, "
         "English)."),
}

#: The number of entries of HAND_WRITTEN: it only goes down.
HAND_WRITTEN_CEILING = 26

#: (b) A tree that is not a screen: what it computes, and why no screen is needed.
MINIMAL_TREES: dict[str, tuple[int, str]] = {
    "tests/unit/bridges/compat/diagnostics/test_action_runner_traces.py":
        (4, "the Lab runner's traces and artifacts: the dump is carried, never read."),
    "tests/unit/bridges/compat/diagnostics/test_selector_test_production.py":
        (1, "the selector bench's plumbing (overrides, versions, language) with an invented vocabulary."),
    "tests/unit/bridges/compat/diagnostics/test_selector_test_runner.py":
        (2, "the bench evaluates an xpath like d.xpath() does: engine, not screen."),
    "tests/unit/core/test_layout_fingerprint.py":
        (21, "the layout digest: same tree, same digest."),
    "tests/unit/one_path/conftest.py":
        (3, "the recording phone of the one-path tests: the bridge and the CLI see the same screen."),
    "tests/unit/scripts/test_leak_guard.py":
        (4, "the leak guard's clock rule: one status-bar node, its id and its text."),
    "tests/unit/scripts/test_measure_screen_reading.py":
        (3, "the measurement script's read-only guard."),
    "tests/unit/scripts/test_screen_proofs.py":
        (12, "the corpus replay tools' comparison logic; they read the real corpus."),
    "tests/unit/shared/actions/test_funnel_one_photo.py":
        (4, "how many photos the shared funnel takes, not what it reads."),
    "tests/unit/shared/device/test_facade_dump_timeout.py":
        (3, "the dump timeout of the facade: an empty hierarchy."),
    "tests/unit/shared/device/test_snapshot.py":
        (8, "the photo answers like d.xpath() on the same tree: engine equality."),
    "tests/unit/shared/diagnostics/test_screen_ring.py":
        (4, "the ring of screens: folding, skeleton difference, ceiling."),
    "tests/unit/shared/test_screen_snapshot.py":
        (1, "the end-of-run capture file: the dump is stored, never read."),
    "tests/unit/shared/test_ui_dump_normalisation.py":
        (2, "the tree normalisation d.xpath() applies, on the shape of a real dump."),
    "tests/unit/shared/ui/test_language_engine.py":
        (5, "the language scoring rules shared by both platforms."),
    "tests/unit/social_media/instagram/test_feed_suggestions_carousel_framing.py":
        (1,
         "a carousel with no visible band (no feed list, no tab bar): the framing guard; every "
         "real dump carries the list, and the carousel itself is read on real feeds."),
    "tests/unit/social_media/instagram/test_one_dump_readers_on_photo.py":
        (1,
         "an empty hierarchy, what the device answers when it cannot read a screen: the guard of "
         "every reader. The screens read are real (a professional profile, a cut bio, the "
         "activity list) or their clone (the package renamed)."),
    "tests/unit/social_media/instagram/test_feed_suggestions_follow_loop.py":
        (15, "which bounds the finger starts from and what is booked; the parsing is proven elsewhere."),
    "tests/unit/social_media/instagram/test_post_reading_caption.py":
        (2,
         "a caption below the screen: the off-screen guard is geometry, and uiautomator clips its "
         "dump to the screen (no capture holds one); the other readings run on real feeds."),
    "tests/unit/social_media/instagram/test_post_reading_reframe.py":
        (16, "the reframe scroll computed from a caption's bounds."),
    "tests/unit/social_media/tiktok/actions/test_probes_on_one_photo.py":
        (4, "how many photos the TikTok probes take per turn."),
    "tests/unit/social_media/tiktok/test_dump_readers_read_the_d_xpath_tree.py":
        (8, "the dump readers evaluate on the tree d.xpath() sees: engine equality."),
    "tests/unit/social_media/tiktok/workflows/for_you/test_feed_turn_reads_one_photo.py":
        (3, "how many photos a feed turn takes."),
    "tests/unit/social_media/youtube/workflows/account/test_youtube_account_workflow.py":
        (1, "an empty hierarchy: the account flow never reads it."),
    "tests/unit/test_ui_language_hardening.py":
        (2, "apostrophe folding of the selectors, on one row."),
}

#: (c) An excerpt copied from a real dump, inline; new ones go to fixtures/.
DUMP_EXCERPTS: dict[str, tuple[int, str]] = {
    "tests/unit/social_media/instagram/test_own_avatar_from_tab.py":
        (1, "own profile of Instagram 410 in French, trimmed to the two avatars, bounds kept."),
    "tests/unit/social_media/instagram/workflows/test_comments_thread_parsing.py":
        (3, "comment thread copied from a device dump, trimmed to its rows."),
    "tests/unit/social_media/tiktok/ui/test_tiktok_43_1_4_search_rows.py":
        (3, "Users tab of TikTok 43.1.4 (Pixel 3a, French), anonymized, ids and bounds kept."),
    "tests/unit/social_media/tiktok/ui/test_tiktok_47_0_3_screens.py":
        (5,
         "search row, profile counters and Message entry of TikTok 47.0.3 (Pixel 6a, French), "
         "anonymized."),
}


def _docstrings(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


@lru_cache(maxsize=None)
def markup_literals(source: str) -> int:
    """How many string literals of a Python source carry screen markup (docstrings aside)."""
    try:
        tree = ast.parse(source.lstrip("﻿"))
    except SyntaxError:
        return 0
    docstrings = _docstrings(tree)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values
                           if isinstance(v, ast.Constant) and isinstance(v.value, str))
        else:
            continue
        count += bool(MARKUP.search(text))
    return count


def fixture_problem(relative: str, content: bytes) -> str | None:
    """Why an .xml under tests/ is not a real dump, or None."""
    if "fixtures" not in Path(relative).parts[:-1]:
        return "outside a fixtures/ folder"
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError as error:
        return f"not XML ({error})"
    if root.tag != "hierarchy" or root.get("rotation") is None:
        return "no <hierarchy rotation=...> root"
    nodes = list(root.iter("node"))
    if not nodes:
        return "no node"
    for node in nodes:
        missing = [a for a in DUMP_ATTRIBUTES if node.get(a) is None]
        if missing:
            return f"a node lacks what the device writes ({', '.join(missing)})"
    return None


def read_tree() -> tuple[dict[str, str], dict[str, bytes]]:
    sources, fixtures = {}, {}
    for path in TESTS.rglob("*"):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        relative = path.relative_to(CORE).as_posix()
        if path.suffix == ".py":
            sources[relative] = path.read_text(encoding="utf-8-sig", errors="replace")
        elif path.suffix == ".xml":
            fixtures[relative] = path.read_bytes()
    return sources, fixtures


LISTS = (("HAND_WRITTEN", HAND_WRITTEN), ("MINIMAL_TREES", MINIMAL_TREES), ("DUMP_EXCERPTS", DUMP_EXCERPTS))


def check(sources: dict[str, str], fixtures: dict[str, bytes], lists=LISTS,
          hand_written_ceiling: int = HAND_WRITTEN_CEILING) -> list[str]:
    failures = []
    listed = {}
    for name, entries in lists:
        for path, (ceiling, _reason) in entries.items():
            if path in listed:
                failures.append(f"{path} is in {listed[path][0]} and in {name}: one list only")
            listed[path] = (name, ceiling)

    for path in sorted(set(sources) | set(listed)):
        count = markup_literals(sources[path]) if path in sources else 0
        if path not in listed:
            if count:
                failures.append(
                    f"{path}: {count} screen(s) written in the test. A screen test reads a real dump, "
                    f"anonymized (scripts/anonymize_dump.py), from a fixtures/ folder; a tree that is not a "
                    f"screen goes to MINIMAL_TREES with what it computes.")
            continue
        name, ceiling = listed[path]
        if path not in sources:
            failures.append(f"{path} ({name}) no longer exists: drop the entry")
        elif count > ceiling:
            failures.append(f"{path} ({name}) writes {count} screen literal(s), ceiling {ceiling}: "
                            f"a new screen goes to fixtures/ as a real dump")
        elif count == 0:
            failures.append(f"{path} ({name}) writes no screen any more: drop the entry")
        elif count < ceiling:
            failures.append(f"{path} ({name}) went down to {count} (ceiling {ceiling}): lower the ceiling")

    hand_written = dict(lists)["HAND_WRITTEN"]
    if len(hand_written) > hand_written_ceiling:
        failures.append(f"HAND_WRITTEN holds {len(hand_written)} entries, ceiling {hand_written_ceiling}: "
                        f"the list only shrinks")
    elif len(hand_written) < hand_written_ceiling:
        failures.append(f"HAND_WRITTEN went down to {len(hand_written)}: set HAND_WRITTEN_CEILING to it")

    for path, content in sorted(fixtures.items()):
        problem = fixture_problem(path, content)
        if problem:
            failures.append(f"{path}: {problem}. A fixture is a real dump, anonymized.")
    return failures


def main() -> int:
    sources, fixtures = read_tree()
    failures = check(sources, fixtures)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    counts = {name: len(entries) for name, entries in LISTS}
    print(f"Screen test fixtures OK ({len(fixtures)} real dump(s) in fixtures/; hand-written screens "
          f"{counts['HAND_WRITTEN']}, minimal trees {counts['MINIMAL_TREES']}, dump excerpts "
          f"{counts['DUMP_EXCERPTS']})")
    return 0


def inventory() -> int:
    sources, fixtures = read_tree()
    names = {path: name for name, entries in LISTS for path in entries}
    rows = [(path, markup_literals(src)) for path, src in sorted(sources.items())]
    for path, count in rows:
        if count:
            print(f"{count:4d}  {names.get(path, 'UNLISTED'):14s} {path}")
    dumps = {Path(path).name for path in fixtures}
    readers = sorted(p for p, s in sources.items() if any(name in s for name in dumps))
    for path in readers:
        print(f"      {'reads dumps':14s} {path}")
    print(f"\n{sum(1 for _, c in rows if c)} file(s) write markup; {len(readers)} file(s) read the "
          f"{len(fixtures)} fixture dump(s).")
    return 0


def self_test_cases(sources: dict[str, str], fixtures: dict[str, bytes]) -> dict[str, dict]:
    """Each fake must turn the gate red; the real tree, unchanged, must not."""
    dump = next(iter(sorted(fixtures.items())))[1]
    hand_path = next(iter(HAND_WRITTEN))
    new_test = "tests/unit/test_new_fake_screen.py"
    fake_screen = "SCREEN = '<hierarchy rotation=\"0\"><node text=\"Follow\" /></hierarchy>'\n"
    fake_builder = "def _node(t):\n    return f'<node class=\"android.widget.TextView\" text=\"{t}\" />'\n"
    no_attributes = (b'<?xml version="1.0"?><hierarchy rotation="0">'
                     b'<node text="Follow" bounds="[0,0][1,1]"/></hierarchy>')
    trimmed = {path: entry for path, entry in HAND_WRITTEN.items() if path != hand_path}
    grown = {**HAND_WRITTEN, new_test: (1, "a new entry")}
    return {
        "a new test with an inline screen": {"sources": {**sources, new_test: fake_screen}},
        "a new test with a node builder": {"sources": {**sources, new_test: fake_builder}},
        "a listed file that writes one more screen": {
            "sources": {**sources, hand_path: sources[hand_path] + "\n" + fake_screen}},
        "a listed file that writes no screen any more": {"sources": {**sources, hand_path: "X = 1\n"}},
        "an entry added beyond the ceiling": {
            "sources": {**sources, new_test: fake_screen},
            "lists": (("HAND_WRITTEN", grown), LISTS[1], LISTS[2])},
        "an entry dropped without lowering the ceiling": {
            "sources": {**sources, hand_path: "X = 1\n"},
            "lists": (("HAND_WRITTEN", trimmed), LISTS[1], LISTS[2])},
        "a hand-written fixture": {"fixtures": {**fixtures, "tests/unit/x/fixtures/fake.xml": no_attributes}},
        "a real dump outside fixtures/": {"fixtures": {**fixtures, "tests/unit/x/dump.xml": dump}},
    }


def self_test() -> int:
    sources, fixtures = read_tree()
    cases = self_test_cases(sources, fixtures)
    missed = [name for name, fake in cases.items()
              if not check(fake.get("sources", sources), fake.get("fixtures", fixtures),
                           fake.get("lists", LISTS))]
    copy = {**fixtures, "tests/unit/x/fixtures/copy.xml": next(iter(fixtures.values()))}
    control = check(sources, copy)
    if missed or control:
        for name in missed:
            print(f"Self-test FAILED, not caught: {name}")
        for failure in control:
            print(f"Self-test FAILED, a real dump copied into fixtures/ turned it red: {failure}")
        return 1
    print(f"Screen test fixtures self-test OK ({len(cases)} fakes caught, "
          f"a real dump accepted)")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    raise SystemExit(inventory() if "--inventory" in sys.argv else main())
