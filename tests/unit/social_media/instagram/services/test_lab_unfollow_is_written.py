"""The Lab's unfollow is the unfollow engine's, and it is written in the base.

`profile.click_unfollow` tapped the "Following" button of the open profile's header through an
atomic no workflow uses (`click_unfollow_button`): it opened the sheet whose first line
unfollows, and wrote nothing. The production unfollow is the engine's (`UnfollowBusiness`): the
account's row in OUR following list, every check, the row read again, then the UNFOLLOW interaction
and the following row closed. The Lab action now reads the open profile's handle with the
production reader and hands it to that engine, as `engagement.unfollow_account` does with a handle
given; both refuse before any gesture without an account, and say what the base holds after them.

The screens are real Instagram 410.0.0.53.71 captures, anonymized: a profile we follow in English
(Pixel 3a, its header button "Following"), and our following list in French (Pixel 3). The phone
replays the capture behind the clone proxy and the facade the Lab mounts; the base is a throwaway
file. What the row shows after the tap is the one thing no capture holds: its reading
(`_wait_row_unfollowed`, the production read of the row) is answered "follow".
"""

import sqlite3
import time

import pytest

from bridges.tools.lab.actions.instagram.engagement import unfollow_account
from bridges.tools.lab.actions.instagram.profile import click_unfollow
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.tools.lab.action_test.runner import _bind_bundle_account
from profile_posts_phone import ProfilePostsPhone, capture
from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale

ACCOUNT = "lab_tester"
FOLLOWED_PROFILE = ("ig410_en_profile_following.xml", "en", 2220, "user_1")
HEADER_BUTTON = (33, 966, 532, 1054)
FOLLOWING_LIST = ("ig410_fr_following_list_sorted_default.xml", "fr", 2160)
#: The first row of that list: its handle and its button.
LISTED, LISTED_BUTTON = "user_2", (650, 1021, 958, 1109)


@pytest.fixture(autouse=True)
def _throwaway_base_and_no_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "lab.db"))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    before = active_locale()
    yield tmp_path / "lab.db"
    set_active_locale(before)


def _lab_on(screen: str, language: str, height: int, params: dict):
    """The Lab's bundle on a phone showing `screen`, bound as the runner binds it before an action."""
    set_active_locale(language)
    phone = ProfilePostsPhone(screen=capture(screen), height=height)
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    _bind_bundle_account(bundle, params)
    return phone, bundle


def _taps_inside(phone, box):
    left, top, right, bottom = box
    return [tap for tap in phone.taps if left <= tap[1] <= right and top <= tap[2] <= bottom]


class _EngineSpy:
    """Stands for `unfollow_listed_accounts`: what the engine was asked, and its stats."""

    def __init__(self):
        self.calls = []

    def __call__(self, usernames, config=None):
        self.calls.append((list(usernames), dict(config or {})))
        return {"candidates": len(usernames), "unfollows_made": 0, "success": True}


def test_the_profile_unfollow_hands_the_open_profile_to_the_engine():
    screen, language, height, handle = FOLLOWED_PROFILE
    params = {"account": ACCOUNT}
    phone, bundle = _lab_on(screen, language, height, params)
    engine = _EngineSpy()
    bundle.unfollow.unfollow_listed_accounts = engine

    result = click_unfollow(bundle, params)

    # Production never unfollows from a profile's header: nothing tapped there.
    assert _taps_inside(phone, HEADER_BUTTON) == []
    assert engine.calls == [([handle], {"unfollow_mode": "all"})]
    assert result["success"] is False  # the engine made no unfollow
    assert result["details"]["username"] == handle


def test_without_an_account_nothing_is_tapped_and_the_engine_is_not_asked():
    screen, language, height, _handle = FOLLOWED_PROFILE
    phone, bundle = _lab_on(screen, language, height, {})
    engine = _EngineSpy()
    bundle.unfollow.unfollow_listed_accounts = engine

    result = click_unfollow(bundle, {})

    assert phone.taps == []
    assert engine.calls == []
    assert result["success"] is False and "account" in result["message"]


def test_an_unfollow_the_base_does_not_hold_is_not_a_success():
    """The engine says it unfollowed, but nothing was written: the Lab says so."""
    screen, language, height, handle = FOLLOWED_PROFILE
    params = {"account": ACCOUNT}
    _phone, bundle = _lab_on(screen, language, height, params)
    bundle.unfollow.unfollow_listed_accounts = lambda usernames, config=None: {"unfollows_made": 1}
    InstagramFollowGraphService.upsert_following(handle, "", bundle.unfollow._get_account_id())

    result = click_unfollow(bundle, params)

    assert result["success"] is False
    assert result["details"]["recorded"] == {"unfollow_interaction": False, "following_row_closed": False}
    assert "NOT fully written" in result["message"]


def test_a_handle_given_without_an_account_is_not_unfollowed():
    screen, language, height = FOLLOWING_LIST
    phone, bundle = _lab_on(screen, language, height, {})

    result = unfollow_account(bundle, {"username": LISTED})

    assert phone.taps == []
    assert result["success"] is False and "account" in result["message"]


def test_an_account_given_to_an_earlier_action_is_not_used_by_a_later_one():
    """The Lab session keeps its bundle from one action to the next."""
    screen, language, height = FOLLOWING_LIST
    phone, bundle = _lab_on(screen, language, height, {"account": ACCOUNT})
    _bind_bundle_account(bundle, {})

    result = unfollow_account(bundle, {"username": LISTED})

    assert phone.taps == []
    assert result["success"] is False and "account" in result["message"]


def _unfollows_in_base(base, handle):
    con = sqlite3.connect(str(base))
    try:
        return con.execute(
            "SELECT i.interaction_type, i.success FROM interactions i "
            "JOIN social_profiles p ON p.legacy_profile_id = i.profile_id AND p.platform = i.platform "
            "JOIN accounts a ON a.legacy_account_id = i.account_id AND a.platform = i.platform "
            "WHERE i.platform = 'instagram' AND a.username = ? AND p.username = ?",
            (ACCOUNT, handle)).fetchall()
    finally:
        con.close()


def test_the_labs_unfollow_is_written_as_the_engines(_throwaway_base_and_no_pause, monkeypatch):
    base = _throwaway_base_and_no_pause
    screen, language, height = FOLLOWING_LIST
    params = {"account": ACCOUNT, "username": LISTED, "skip_verified": "false"}
    phone, bundle = _lab_on(screen, language, height, params)
    engine = bundle.unfollow
    # Our profile and its following list are opened by navigation the replayed phone has no
    # screens for: the list is the capture already on screen.
    monkeypatch.setattr(engine.nav_actions, "navigate_to_profile_tab", lambda: True)
    monkeypatch.setattr(engine.nav_actions, "open_following_list", lambda: True)
    monkeypatch.setattr(engine, "_wait_row_unfollowed", lambda _username, timeout=None: "follow")
    # The base knows the account as followed, as a sync of the list leaves it.
    InstagramFollowGraphService.upsert_following(LISTED, "", engine._get_account_id())

    result = unfollow_account(bundle, params)

    assert len(phone.taps) == 1 and _taps_inside(phone, LISTED_BUTTON) == phone.taps
    assert _unfollows_in_base(base, LISTED) == [("UNFOLLOW", 1)]
    assert LISTED not in InstagramFollowGraphService.get_active_following_usernames(engine._get_account_id())
    assert result["success"] is True, result
    assert result["details"]["recorded"] == {"unfollow_interaction": True, "following_row_closed": True}
