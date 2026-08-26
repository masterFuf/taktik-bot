"""Collecting a target's posts: open, read the two counters, copy the link, store.

Two consecutive cells that will not open mean the grid is exhausted. A post whose link
cannot be copied is counted, not stored — a row without a URL is useless to a post_url run.
Private accounts and failed navigations are reported, not crashed on.
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
    """Answers like the production ones: atomic pair, or two separate reads that say 0."""

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


class _Harness(ProfilePostsScrapingMixin):
    def __init__(self, repo, config, extractors=None, private=False, navigable=True):
        self.config = config
        self.logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, debug=lambda *a: None)
        self.device = _Device()
        self.nav_actions = SimpleNamespace(navigate_to_profile=lambda u: navigable)
        self.detection_actions = SimpleNamespace(is_post_grid_visible=lambda: True)
        self.profile_manager = SimpleNamespace(
            get_complete_profile_info=lambda **k: {"is_private": private, "posts_count": 0},
        )
        self.ui_extractors = extractors or _Extractors(atomic={"likes": 96, "comments": 9})
        self._ipc = _Ipc()
        self.scraped_posts = []
        self._repo = repo

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


def _wire(monkeypatch, urls, openable=None):
    """`urls[i]` is what the share sheet yields on post #i+1 (None = could not copy)."""
    opened = []

    def open_post(device, index, logger=None):
        ok = True if openable is None else openable(index)
        if ok:
            opened.append(index)
        return ok

    def share_url(device, logger=None):
        position = len(opened) - 1
        return urls[position] if position < len(urls) else None

    monkeypatch.setattr(mod, "open_post_at_position", open_post)
    monkeypatch.setattr(mod, "get_post_url_from_share", share_url)
    return opened


def test_each_post_is_stored_with_its_url_and_counters(monkeypatch):
    repo = _Repo()
    urls = ["https://www.instagram.com/p/A/?igsh=x", "https://www.instagram.com/reel/B/"]
    opened = _wire(monkeypatch, urls)
    h = _Harness(repo, {"target_usernames": ["@Nike"], "max_posts_per_target": 2})

    result = h._scrape_profile_posts()

    assert result["success"] is True and result["total_scraped"] == 2
    assert opened == [1, 2]
    assert [r["post_url"] for r in repo.records] == urls
    # The account is known from the profile we walked — never read off the screen.
    assert {r["author_username"] for r in repo.records} == {"@Nike"}
    assert repo.records[0]["likes_count"] == 96 and repo.records[0]["comments_count"] == 9
    assert [e[0] for e in h._ipc.events] == ["post_captured", "post_captured"]
    assert result["targets_info"][0]["collected"] == 2


def test_a_post_whose_link_cannot_be_copied_is_counted_not_stored(monkeypatch):
    repo = _Repo()
    _wire(monkeypatch, [None])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1})

    result = h._scrape_profile_posts()

    assert repo.records == [] and result["total_scraped"] == 0
    assert result["targets_info"][0]["no_url"] == 1


def test_two_cells_that_will_not_open_end_the_target(monkeypatch):
    repo = _Repo()
    opened = _wire(monkeypatch, ["https://www.instagram.com/p/A/"] * 10, openable=lambda i: i <= 1)
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 10})

    result = h._scrape_profile_posts()

    assert opened == [1]
    assert result["targets_info"][0]["opened"] == 1 and result["total_scraped"] == 1


def test_the_viewer_is_left_after_every_post_even_when_reading_fails(monkeypatch):
    """Opening a post leaves the grid; a back press returns to it. Every opened post must be
    followed by that press, even when its counters or link could not be read."""
    repo = _Repo()
    screen = {"on_grid": True}
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 2})
    h.detection_actions = SimpleNamespace(is_post_grid_visible=lambda: screen["on_grid"])
    h.device.press = lambda key: (h.device.presses.append(key), screen.update(on_grid=True))

    def open_post(device, index, logger=None):
        screen["on_grid"] = False
        return True

    monkeypatch.setattr(mod, "open_post_at_position", open_post)
    monkeypatch.setattr(mod, "get_post_url_from_share",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("share sheet stuck")))

    result = h._scrape_profile_posts()

    assert h.device.presses == ["back", "back"]
    assert screen["on_grid"] is True
    assert result["targets_info"][0]["opened"] == 2 and result["total_scraped"] == 0


def test_private_and_unreachable_accounts_are_reported(monkeypatch):
    opened = _wire(monkeypatch, ["https://www.instagram.com/p/A/"])
    private = _Harness(_Repo(), {"target_usernames": ["alice"]}, private=True)
    unreachable = _Harness(_Repo(), {"target_usernames": ["bob"]}, navigable=False)

    assert private._scrape_profile_posts()["targets_info"][0]["error"] == "private"
    assert unreachable._scrape_profile_posts()["targets_info"][0]["error"] == "navigation failed"
    assert opened == []


def test_nothing_is_stored_when_persistence_is_off(monkeypatch):
    repo = _Repo()
    _wire(monkeypatch, ["https://www.instagram.com/p/A/"])
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
    _wire(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["a"], "max_posts_per_target": 1}, extractors=extractors)

    h._scrape_profile_posts()

    assert extractors.calls == ["atomic"]
    assert (repo.records[0]["likes_count"], repo.records[0]["comments_count"]) == (12, 3)


def test_unreadable_counters_are_none_not_zero(monkeypatch):
    """The separate extractors answer 0 when they find nothing: a double zero is a failed
    read, and must not be written over a value already stored."""
    repo = _Repo()
    extractors = _Extractors(atomic=None, likes=0, comments=0)
    _wire(monkeypatch, ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["a"], "max_posts_per_target": 1}, extractors=extractors)

    h._scrape_profile_posts()

    assert (repo.records[0]["likes_count"], repo.records[0]["comments_count"]) == (None, None)


def test_a_single_readable_counter_is_kept(monkeypatch):
    repo = _Repo()
    extractors = _Extractors(atomic=None, likes=120, comments=0)
    _wire(monkeypatch, ["https://www.instagram.com/p/A/"])
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
