"""The Lab's follow is the workflows' follow, and it is written in the base.

The unfollow in "the bot's follows only" mode undoes an account only when the base holds the bot's
successful FOLLOW of it and our following row. A campaign that prepares its follows from the
Cartography Lab needs those rows. The Lab's `profile.click_follow` only tapped a button through an
atomic no workflow uses (`click_follow_button`): the gesture was real, the base knew nothing, and
the unfollow then protected every one of those accounts as "not followed by the bot". Reading no
relationship first, it also tapped the "Following" button of a profile we already follow, the
button whose sheet unfollows.

It now runs the production follow of a profile (`_do_follow` of the interaction engine, the Lab's
`a.popup`), bound to the account under test the way the Lab runner binds every action. The screens
are real Instagram 410.0.0.53.71 profiles, anonymized: a "Follow" profile under its "Followed by"
line in English and in French (Pixel 3), a "Following" profile (Pixel 3a). The phone replays the
capture (`ProfilePostsPhone`) behind the clone proxy and the facade the Lab mounts; the base is a
throwaway file.
"""

import sqlite3
import time

import pytest

from bridges.compat.diagnostics.actions.instagram.profile import click_follow
from bridges.compat.diagnostics.actions.instagram.unfollow import plan as unfollow_plan
from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.compat.diagnostics.runtime.action_test.runner import _bind_bundle_account
from profile_posts_phone import ProfilePostsPhone, capture
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale

ACCOUNT = "lab_tester"

#: (capture, language, its screen height, the handle its action bar shows, the button's bounds)
FRESH_PROFILES = [
    ("ig410_en_profile_follow_with_mutuals.xml", "en", 2160, "name_36", (33, 877, 480, 965)),
    ("ig410_fr_profile_follow_with_mutuals.xml", "fr", 2160, "name_1", (33, 878, 325, 966)),
]


@pytest.fixture(autouse=True)
def _throwaway_base_and_no_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "lab.db"))
    # The human pauses of the tap and of the checks are not what is tested here.
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


def _rows(base, sql, args=()):
    con = sqlite3.connect(str(base))
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, args)]
    finally:
        con.close()


def _follows_in_base(base, handle):
    return _rows(base, (
        "SELECT i.interaction_type, i.success FROM interactions i "
        "JOIN social_profiles p ON p.legacy_profile_id = i.profile_id AND p.platform = i.platform "
        "JOIN accounts a ON a.legacy_account_id = i.account_id AND a.platform = i.platform "
        "WHERE i.platform = 'instagram' AND a.username = ? AND p.username = ?"), (ACCOUNT, handle))


def _following_rows(base, handle):
    return _rows(base, (
        "SELECT followed_by_bot, source, unfollowed_at FROM social_graph_sync "
        "WHERE platform = 'instagram' AND direction = 'following' AND username = ?"), (handle,))


def _taps_inside(phone, box):
    left, top, right, bottom = box
    return [tap for tap in phone.taps if left <= tap[1] <= right and top <= tap[2] <= bottom]


@pytest.mark.parametrize("screen, language, height, handle, button", FRESH_PROFILES,
                         ids=["en", "fr"])
def test_the_labs_follow_is_written_as_the_bots(_throwaway_base_and_no_pause, screen, language,
                                                height, handle, button):
    base = _throwaway_base_and_no_pause
    phone, bundle = _lab_on(screen, language, height, {"account": ACCOUNT})

    result = click_follow(bundle, {"account": ACCOUNT})

    assert _follows_in_base(base, handle) == [{"interaction_type": "FOLLOW", "success": 1}]
    assert _following_rows(base, handle) == [
        {"followed_by_bot": 1, "source": "bot_follow", "unfollowed_at": None}]
    # One tap, on the header's follow button.
    assert len(phone.taps) == 1 and _taps_inside(phone, button) == phone.taps
    assert result["success"] is True, result
    assert result["details"]["username"] == handle
    assert result["details"]["state_before"] == "follow"
    assert result["details"]["recorded"] == {"follow_interaction": True, "following_row": True}


def test_the_unfollow_of_the_bots_follows_finds_it(_throwaway_base_and_no_pause):
    """The campaign's chain: a Lab follow, then the unfollow's decision on the base alone."""
    screen, language, height, handle, _button = FRESH_PROFILES[0]
    params = {"account": ACCOUNT}
    _phone, bundle = _lab_on(screen, language, height, params)

    click_follow(bundle, params)
    decision = unfollow_plan(bundle, {**params, "unfollow_mode": "all", "bot_follows_only": "true",
                                      "min_days_since_follow": "0"})

    assert handle in decision["details"]["candidates"]
    assert decision["details"]["refusals"].get("not_followed_by_bot", 0) == 0


def test_a_profile_we_already_follow_is_left_alone(_throwaway_base_and_no_pause):
    """Its header button is "Following": a tap there opens the sheet whose first line unfollows."""
    base = _throwaway_base_and_no_pause
    phone, bundle = _lab_on("ig410_en_profile_following.xml", "en", 2220, {"account": ACCOUNT})

    result = click_follow(bundle, {"account": ACCOUNT})

    assert phone.taps == []
    assert _follows_in_base(base, "user_1") == []
    assert _following_rows(base, "user_1") == []
    assert result["success"] is False
    assert result["details"]["state_before"] == "following"


def test_without_an_account_nothing_is_tapped(_throwaway_base_and_no_pause):
    """A follow the base does not hold is one the unfollow of the bot's follows never undoes."""
    screen, language, height, _handle, _button = FRESH_PROFILES[0]
    phone, bundle = _lab_on(screen, language, height, {})

    result = click_follow(bundle, {})

    assert phone.taps == []
    assert result["success"] is False
    assert "account" in result["message"]

