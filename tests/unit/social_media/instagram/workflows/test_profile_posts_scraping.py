"""The profile-posts source walks a grid and writes cards, paying the share sheet only when it must.

A post the catalogue already holds is recognised by its author + caption identity BEFORE the
share sheet, and only refreshed; a post with a caption too weak to identify pays the sheet
rather than risk refreshing the wrong row. Two consecutive cells that will not open mean the
grid is exhausted. Private accounts and failed navigations are reported, not crashed on.
"""

from types import SimpleNamespace

import pytest

from taktik.core.social_media.instagram.workflows.common.post_card import PostCard
from taktik.core.social_media.instagram.workflows.scraping import profile_posts_scraping as mod
from taktik.core.social_media.instagram.workflows.scraping.profile_posts_scraping import (
    ProfilePostsScrapingMixin,
)

STRONG = "Nouvelle collection printemps disponible en boutique"


def _card(author="alice", caption=STRONG, likes=10, comments=2, reel=False):
    ref = f"{author}:{abs(hash(caption)) % 10**12:012d}" if caption else author
    return PostCard(author, reel, likes, comments, caption, None, None, ref, True)


class _Repo:
    def __init__(self, known_refs=()):
        self.known = {ref: {"post_url": f"https://www.instagram.com/p/known_{i}/"} for i, ref in enumerate(known_refs)}
        self.records, self.refreshes, self.lookups = [], [], []

    def find_by_ref(self, ref, platform="instagram"):
        self.lookups.append(ref)
        return self.known.get(ref)

    def refresh_counts_by_ref(self, ref, likes, comments, platform="instagram", scraping_id=None):
        self.refreshes.append((ref, likes, comments, scraping_id))
        return True

    def record(self, **kwargs):
        self.records.append(kwargs)
        return len(self.records)


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
    def __init__(self, repo, config, private=False, navigable=True):
        self.config = config
        self.logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, debug=lambda *a: None)
        self.device = _Device()
        self.nav_actions = SimpleNamespace(navigate_to_profile=lambda u: navigable)
        self.detection_actions = SimpleNamespace(is_post_grid_visible=lambda: True)
        self.profile_manager = SimpleNamespace(
            get_complete_profile_info=lambda **k: {"is_private": private, "posts_count": 0},
        )
        self.ui_extractors, self.scroll_actions = object(), object()
        self.scraping_session_id = 7
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


def _wire(monkeypatch, cards, urls=None, openable=None):
    """`cards[i]` is what post #i+1 reads; `urls[i]` what its share sheet yields."""
    opened = []
    url_reads = []

    def open_post(device, index, logger=None):
        ok = True if openable is None else openable(index)
        if ok:
            opened.append(index)
        return ok

    def read_card(device, logger=None, **kwargs):
        assert kwargs["with_url"] is False   # the sheet is never paid inside the card read
        return cards[len(opened) - 1]

    def read_url(device, logger=None):
        url_reads.append(len(opened))
        return (urls or [])[len(opened) - 1] if urls and len(opened) <= len(urls) else None

    monkeypatch.setattr(mod, "open_post_at_position", open_post)
    monkeypatch.setattr(mod, "read_open_post_card", read_card)
    monkeypatch.setattr(mod, "read_open_post_url", read_url)
    return opened, url_reads


def test_new_posts_are_catalogued_with_their_url_and_position(monkeypatch):
    repo = _Repo()
    cards = [_card(likes=300, comments=4), _card(caption="Behind the scenes de notre atelier ce matin", reel=True)]
    urls = ["https://www.instagram.com/p/A/?igsh=x", "https://www.instagram.com/reel/B/"]
    opened, url_reads = _wire(monkeypatch, cards, urls)
    h = _Harness(repo, {"target_usernames": ["@Nike"], "max_posts_per_target": 2})

    result = h._scrape_profile_posts()

    assert result["success"] is True and result["total_scraped"] == 2
    assert opened == [1, 2] and url_reads == [1, 2]
    assert [r["post_url"] for r in repo.records] == urls
    assert [r["grid_position"] for r in repo.records] == [1, 2]
    assert [r["post_type"] for r in repo.records] == ["post", "reel"]
    assert repo.records[0]["scraping_id"] == 7 and repo.records[0]["likes_count"] == 300
    assert [e[0] for e in h._ipc.events] == ["post_captured", "post_captured"]
    assert h._ipc.events[0][1]["status"] == "recorded" and h._ipc.events[0][1]["position"] == 1
    assert result["targets_info"][0]["recorded"] == 2


def test_a_known_post_is_refreshed_without_paying_the_share_sheet(monkeypatch):
    card = _card()
    repo = _Repo(known_refs=[card.post_ref])
    _, url_reads = _wire(monkeypatch, [card], ["https://www.instagram.com/p/X/"])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1})

    result = h._scrape_profile_posts()

    assert url_reads == []
    assert repo.records == []
    assert repo.refreshes == [(card.post_ref, 10, 2, 7)]
    assert result["targets_info"][0]["refreshed"] == 1
    assert h._ipc.events[0][1]["post_url"] == "https://www.instagram.com/p/known_0/"


def test_a_known_post_is_left_alone_when_refresh_is_off(monkeypatch):
    card = _card()
    repo = _Repo(known_refs=[card.post_ref])
    _, url_reads = _wire(monkeypatch, [card], ["https://www.instagram.com/p/X/"])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1, "refresh_known": False})

    result = h._scrape_profile_posts()

    assert url_reads == [] and repo.refreshes == [] and repo.records == []
    assert result["targets_info"][0]["skipped_known"] == 1


def test_a_weak_caption_never_trusts_the_identity_lookup(monkeypatch):
    card = _card(caption="Merci !")
    repo = _Repo(known_refs=[card.post_ref])   # would be a hit — must not be consulted
    _, url_reads = _wire(monkeypatch, [card], ["https://www.instagram.com/p/W/"])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1})

    h._scrape_profile_posts()

    assert repo.lookups == [] and url_reads == [1]
    assert repo.records[0]["post_url"] == "https://www.instagram.com/p/W/"


def test_a_post_without_share_url_is_counted_not_written(monkeypatch):
    repo = _Repo()
    _wire(monkeypatch, [_card()], [None])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1})

    result = h._scrape_profile_posts()

    assert repo.records == [] and result["total_scraped"] == 0
    assert result["targets_info"][0]["no_url"] == 1


def test_two_cells_that_will_not_open_end_the_target(monkeypatch):
    repo = _Repo()
    opened, _ = _wire(monkeypatch, [_card()] * 10, ["https://www.instagram.com/p/A/"] * 10,
                      openable=lambda index: index <= 1)
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 10})

    result = h._scrape_profile_posts()

    assert opened == [1]
    assert result["targets_info"][0]["opened"] == 1 and result["total_scraped"] == 1


def test_the_viewer_is_left_after_every_post_even_when_reading_fails(monkeypatch):
    """Opening a post leaves the grid; a back press returns to it. Every opened post must be
    followed by that press, even when its card could not be read."""
    repo = _Repo()
    screen = {"on_grid": True}
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 2})
    h.detection_actions = SimpleNamespace(is_post_grid_visible=lambda: screen["on_grid"])
    h.device.press = lambda key: (h.device.presses.append(key), screen.update(on_grid=True))

    def open_post(device, index, logger=None):
        screen["on_grid"] = False
        return True

    monkeypatch.setattr(mod, "open_post_at_position", open_post)
    monkeypatch.setattr(mod, "read_open_post_card", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dump failed")))

    result = h._scrape_profile_posts()

    assert h.device.presses == ["back", "back"]
    assert screen["on_grid"] is True
    assert result["targets_info"][0]["opened"] == 2 and result["total_scraped"] == 0


def test_private_and_unreachable_accounts_are_reported(monkeypatch):
    opened, _ = _wire(monkeypatch, [_card()], ["https://www.instagram.com/p/A/"])
    private = _Harness(_Repo(), {"target_usernames": ["alice"]}, private=True)
    unreachable = _Harness(_Repo(), {"target_usernames": ["bob"]}, navigable=False)

    assert private._scrape_profile_posts()["targets_info"][0]["error"] == "private"
    assert unreachable._scrape_profile_posts()["targets_info"][0]["error"] == "navigation failed"
    assert opened == []


def test_nothing_is_written_when_persistence_is_off(monkeypatch):
    repo = _Repo()
    _wire(monkeypatch, [_card()], ["https://www.instagram.com/p/A/"])
    h = _Harness(repo, {"target_usernames": ["alice"], "max_posts_per_target": 1, "save_to_db": False})

    result = h._scrape_profile_posts()

    assert repo.records == [] and repo.lookups == []
    assert result["total_scraped"] == 1   # read and reported, not catalogued


def test_no_targets_is_an_error_not_a_run():
    assert _Harness(_Repo(), {"target_usernames": []})._scrape_profile_posts()["success"] is False


# ── Bridge config ────────────────────────────────────────────────────────────

def test_bridge_config_maps_the_profile_posts_source():
    from bridges.instagram.scraping.runtime.config import build_scraping_config

    cfg = build_scraping_config({
        "type": "profile_posts", "targetUsernames": ["nike", "adidas"],
        "maxPostsPerTarget": 5, "refreshKnown": False, "maxProfiles": 500,
    })
    assert cfg["type"] == "profile_posts"
    assert cfg["target_usernames"] == ["nike", "adidas"]
    assert cfg["scrape_type"] == "profile_posts"
    assert cfg["max_posts_per_target"] == 5
    assert cfg["refresh_known"] is False

    defaults = build_scraping_config({"type": "profile_posts", "targetUsernames": ["nike"], "maxPostsPerTarget": 0})
    assert defaults["max_posts_per_target"] == mod.DEFAULT_MAX_POSTS_PER_TARGET
    assert defaults["refresh_known"] is True
