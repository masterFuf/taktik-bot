"""Collecting a target's posts: open the first one, read, copy the link, move to the next.

The walk is the point. Opening the first post is the ONLY grid interaction; from there the
run advances inside the viewer, which is what a human does and what the like workflow
already does. A reel takes the grid route instead — a vertical gesture in the clips viewer
scrolls Instagram's global reels feed and loses the Back control.

The target's profile is never read: it is the subject of the run, not one of its results.
"""

from types import SimpleNamespace

import pytest

from taktik.core.social_media.instagram.workflows.scraping import profile_posts_scraping as mod
from taktik.core.social_media.instagram.workflows.scraping.profile_posts_scraping import (
    ProfilePostsScrapingMixin,
)


class _Repo:
    def __init__(self, fails=False):
        self.records = []
        self._fails = fails

    def record(self, **kwargs):
        self.records.append(kwargs)
        return None if self._fails else len(self.records)


class _Extractors:
    """Answers like the production ones: an atomic pair, or two separate reads."""

    def __init__(self, atomic=None, likes=0, comments=0):
        self._atomic, self._likes, self._comments = atomic, likes, comments
        self.calls = []

    def extract_post_stats_atomic(self):
        self.calls.append("atomic")
        return self._atomic

    def extract_likes_count_from_ui(self, is_reel=None):
        self.calls.append("likes")
        return self._likes

    def extract_comments_count_from_ui(self, is_reel=None):
        self.calls.append("comments")
        return self._comments


class _Navigator:
    """Stands in for the production PostNavigationMixin carrier."""

    def __init__(self, can_open_first=True, advances=None):
        self._can_open_first = can_open_first
        #: One answer per advance; exhausted = no further post.
        self._advances = list(advances if advances is not None else [True] * 50)
        self.opened_first = 0
        self.advance_calls = []

    def _open_first_post_of_profile(self, username=None):
        self.opened_first += 1
        return self._can_open_first

    def _advance_or_exit_reel(self, is_reel, username=None):
        self.advance_calls.append(is_reel)
        return self._advances.pop(0) if self._advances else False


class _Ipc:
    def __init__(self):
        self.events = []

    def send(self, event_type, **payload):
        self.events.append((event_type, payload))


class _Device:
    def __init__(self):
        self.presses = []

    def press(self, key):
        self.presses.append(key)


class _ProfileManager:
    """Records any attempt to read the profile — there should be none."""

    def __init__(self):
        self.calls = 0

    def get_complete_profile_info(self, **kwargs):
        self.calls += 1
        return {"is_private": False, "posts_count": 37}


class _Harness(ProfilePostsScrapingMixin):
    def __init__(self, repo, config, extractors=None, navigator=None, navigable=True):
        self.config = config
        self.logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, debug=lambda *a: None)
        self.device = _Device()
        self.nav_actions = SimpleNamespace(navigate_to_profile=lambda u: navigable)
        self.detection_actions = SimpleNamespace(is_post_grid_visible=lambda: True)
        self.profile_manager = _ProfileManager()
        self.ui_extractors = extractors or _Extractors(atomic={"likes": 96, "comments": 9})
        self._ipc = _Ipc()
        self.scraped_posts = []
        self._repo = repo
        self.navigator = navigator or _Navigator()
        self._post_navigator_instance = self.navigator

    def _local_db(self):
        return SimpleNamespace(social_posts=self._repo)

    def _should_continue(self):
        return True


@pytest.fixture(autouse=True)
def _quiet_device(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_: None)
    monkeypatch.setattr(mod, "detect_and_optimize", lambda device: "fr")
    monkeypatch.setattr(mod, "ensure_profile_grid_tab", lambda device, logger=None: True)
    monkeypatch.setattr(mod, "is_reel_post", lambda device, logger=None: False)


def _urls(monkeypatch, urls):
    """Hand back `urls` in order, one per share-sheet read (None = link not copied)."""
    reads = {"n": 0}

    def share_url(device, logger=None):
        index = reads["n"]
        reads["n"] += 1
        return urls[index] if index < len(urls) else None

    monkeypatch.setattr(mod, "get_post_url_from_share", share_url)
    return reads


# ── The walk ─────────────────────────────────────────────────────────────────

def test_the_first_post_is_opened_once_then_the_run_advances_in_the_viewer(monkeypatch):
    """The grid is touched ONCE. Anything else means hunting cells post by post, which is
    what made the first device run scroll for a minute and open nothing."""
    repo = _Repo()
    navigator = _Navigator()
    _urls(monkeypatch, [f"https://www.instagram.com/p/{c}/" for c in "ABC"])
    h = _Harness(repo, {"target_usernames": ["nike"], "max_posts_per_target": 3}, navigator=navigator)

    result = h._scrape_profile_posts()

    assert navigator.opened_first == 1
    # Two advances for three posts: the last one needs none.
    assert navigator.advance_calls == [False, False]
    assert len(repo.records) == 3
    assert result["targets_info"][0]["collected"] == 3


def test_each_post_is_stored_with_its_url_and_counters(monkeypatch):
    repo = _Repo()
    urls = ["https://www.instagram.com/p/A/?igsh=x", "https://www.instagram.com/reel/B/"]
    _urls(monkeypatch, urls)
    h = _Harness(repo, {"target_usernames": ["@Nike"], "max_posts_per_target": 2})

    result = h._scrape_profile_posts()

    assert result["success"] is True and result["total_scraped"] == 2
    assert [r["post_url"] for r in repo.records] == urls
    # The account is the profile we walked — never read off the screen.
    assert {r["author_username"] for r in repo.records} == {"@Nike"}
    assert repo.records[0]["likes_count"] == 96 and repo.records[0]["comments_count"] == 9
    assert [e[0] for e in h._ipc.events] == ["post_captured", "post_captured"]


def test_the_targets_profile_is_never_read(monkeypatch):
    """Reading it cost seconds per target and announced a captured PROFILE on a run whose
    whole output is post URLs — which is what made the live panel say "1 profile"."""
    h = _Harness(_Repo(), {"target_usernames": ["nike"], "max_posts_per_target": 1})
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])

    h._scrape_profile_posts()

    assert h.profile_manager.calls == 0
    assert [e[0] for e in h._ipc.events] == ["post_captured"]


def test_a_reel_is_advanced_through_the_reel_escape(monkeypatch):
    """The clips viewer is a trap: the production advance must be told it is on a reel so it
    takes the grid route instead of swiping into Instagram's global reels feed."""
    navigator = _Navigator()
    monkeypatch.setattr(mod, "is_reel_post", lambda device, logger=None: True)
    _urls(monkeypatch, ["https://www.instagram.com/reel/A/", "https://www.instagram.com/reel/B/"])
    h = _Harness(_Repo(), {"target_usernames": ["nike"], "max_posts_per_target": 2}, navigator=navigator)

    h._scrape_profile_posts()

    assert navigator.advance_calls == [True]


def test_an_advance_that_goes_nowhere_ends_the_target(monkeypatch):
    repo = _Repo()
    navigator = _Navigator(advances=[True, False])
    _urls(monkeypatch, [f"https://www.instagram.com/p/{c}/" for c in "ABCDE"])
    h = _Harness(repo, {"target_usernames": ["nike"], "max_posts_per_target": 5}, navigator=navigator)

    result = h._scrape_profile_posts()

    assert len(repo.records) == 2
    assert result["targets_info"][0]["opened"] == 2


def test_the_same_post_twice_ends_the_target(monkeypatch):
    """At the end of a profile the viewer stops moving. Recording the post again would
    inflate the run with a row that is already stored."""
    repo = _Repo()
    same = "https://www.instagram.com/p/A/"
    _urls(monkeypatch, [same, same, same])
    h = _Harness(repo, {"target_usernames": ["nike"], "max_posts_per_target": 3})

    result = h._scrape_profile_posts()

    assert len(repo.records) == 1
    assert result["total_scraped"] == 1
    assert result["targets_info"][0]["collected"] == 1


def test_a_post_whose_link_cannot_be_copied_is_counted_not_stored(monkeypatch):
    repo = _Repo()
    _urls(monkeypatch, [None])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1})

    result = h._scrape_profile_posts()

    assert repo.records == [] and result["total_scraped"] == 0
    assert result["targets_info"][0]["no_url"] == 1


def test_a_share_sheet_that_throws_does_not_stop_the_walk(monkeypatch):
    repo = _Repo()
    navigator = _Navigator()
    monkeypatch.setattr(mod, "get_post_url_from_share",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("share sheet stuck")))
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 2}, navigator=navigator)

    result = h._scrape_profile_posts()

    assert result["targets_info"][0]["no_url"] == 2
    assert navigator.advance_calls == [False]


def test_a_profile_whose_first_post_will_not_open_is_reported(monkeypatch):
    """Covers an empty grid and an account whose posts are not served to us."""
    navigator = _Navigator(can_open_first=False)
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(_Repo(), {"target_usernames": ["alice"]}, navigator=navigator)

    result = h._scrape_profile_posts()

    assert result["targets_info"][0]["error"] == "no post reachable"
    assert navigator.advance_calls == []


def test_an_unreachable_account_is_reported(monkeypatch):
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(_Repo(), {"target_usernames": ["bob"]}, navigable=False)

    assert h._scrape_profile_posts()["targets_info"][0]["error"] == "navigation failed"
    assert h.navigator.opened_first == 0


def test_nothing_is_stored_when_persistence_is_off(monkeypatch):
    repo = _Repo()
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1, "save_to_db": False})

    result = h._scrape_profile_posts()

    assert repo.records == []
    assert result["total_scraped"] == 1   # read and reported, not stored


def test_no_targets_is_an_error_not_a_run():
    assert _Harness(_Repo(), {"target_usernames": []})._scrape_profile_posts()["success"] is False


# ── Counter reading ──────────────────────────────────────────────────────────

def test_the_atomic_read_is_preferred_and_the_separate_one_is_not_called(monkeypatch):
    repo = _Repo()
    extractors = _Extractors(atomic={"likes": 12, "comments": 3})
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["a"], "max_posts_per_target": 1}, extractors=extractors)

    h._scrape_profile_posts()

    assert extractors.calls == ["atomic"]
    assert (repo.records[0]["likes_count"], repo.records[0]["comments_count"]) == (12, 3)


def test_unreadable_counters_are_none_not_zero(monkeypatch):
    """The separate extractors answer 0 when they find nothing: a double zero is a failed
    read, and must not be written over a value already stored."""
    repo = _Repo()
    extractors = _Extractors(atomic=None, likes=0, comments=0)
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["a"], "max_posts_per_target": 1}, extractors=extractors)

    h._scrape_profile_posts()

    assert (repo.records[0]["likes_count"], repo.records[0]["comments_count"]) == (None, None)


def test_a_single_readable_counter_is_kept(monkeypatch):
    repo = _Repo()
    extractors = _Extractors(atomic=None, likes=120, comments=0)
    _urls(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["a"], "max_posts_per_target": 1}, extractors=extractors)

    h._scrape_profile_posts()

    assert (repo.records[0]["likes_count"], repo.records[0]["comments_count"]) == (120, 0)


# ── Bridge config ────────────────────────────────────────────────────────────

def test_bridge_config_maps_the_profile_posts_source():
    from bridges.instagram.scraping.runtime.config import build_scraping_config

    cfg = build_scraping_config({
        "type": "profile_posts", "targetUsernames": ["nike", "adidas"],
        "maxPostsPerTarget": 5, "maxProfiles": 500,
    })
    assert cfg["type"] == "profile_posts"
    assert cfg["target_usernames"] == ["nike", "adidas"]
    assert cfg["max_posts_per_target"] == 5

    defaults = build_scraping_config({"type": "profile_posts", "targetUsernames": ["nike"], "maxPostsPerTarget": 0})
    assert defaults["max_posts_per_target"] == mod.DEFAULT_MAX_POSTS_PER_TARGET
