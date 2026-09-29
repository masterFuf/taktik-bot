"""A fans category whose rows could not be read is a failed read, never « 0 fans ».

`scrape_non_followers_category` opens the category « Followers you don't follow back » of our
followers list and records its fans. Its rows were read by `_get_visible_non_follower_usernames`,
which caught any error at debug level and answered « nobody »: the read then ended on its first
screen and was announced as a success with 0 fans, in the log, the Lab (« 0 fans ») and the sync
line the app shows. Seen on the phone of the Lab's tests, which answers no native selector: every
read of a served category failed there, and passed for an empty one.

Now the fans are the rows offering to follow back, read by the list's own row reader
(`_visible_follow_rows`, one dump, the one of the unfollow and the syncs). A screen that could not
be read, or a first screen of the open category without one fan read, is a failed read:
`read_failed`, no count (None), nothing recorded, the error in the log. A category not served stays
« not applicable » (lot bancig): nothing of that changes.

The screens are real dumps, anonymized: our followers list with its categories, Instagram 410 in
English (Pixel 3a), and our French followers list, Instagram 447 (Pixel 6a). No capture of the
category once opened exists yet (lot bancig): the phone here keeps the list on screen after the tap
on the category, and its rows stand in for the category's (the same widgets: the username, and the
« Follow back » / « Suivre en retour » button); the fans read are its rows offering to follow back.
"""

from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions as register_instagram
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parent / "fixtures"
PKG = "com.instagram.android"

#: (capture, app language, the usernames of its rows offering to follow back)
SERVED = [
    ("ig410_en_own_followers_list_categories.xml", "en", ["user_5", "user_6", "user_7", "name_10"]),
    ("ig447_fr_own_followers_list.xml", "fr", ["user_6", "user_7", "user_8"]),
]


class _ListPhone:
    """uiautomator2 as the Lab touches it: `xpath()` on one dump, the taps it would inject. Once
    `stopped`, every dump fails, as when the uiautomator2 server stops answering."""

    wait_timeout = 0.2

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.taps = []
        self.stopped = False

    def dump_hierarchy(self, *_args, **_kwargs):
        if self.stopped:
            raise ConnectionError("uiautomator2 server not answering")
        return self.xml

    def app_current(self):
        return {"package": PKG, "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2220)

    def click(self, x, y):
        self.taps.append((x, y))

    def press(self, key, *_args):
        return True


@pytest.fixture(autouse=True)
def _quick(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    register_instagram()
    yield
    set_active_locale(None)


def _unfollow_on(name, lang, monkeypatch):
    """The Lab's unfollow engine on our followers list: account bound, the follow graph a spy."""
    recorded = []
    monkeypatch.setattr(sync_following, "InstagramFollowGraphService",
                        type("GraphSpy", (), {"upsert_follower": staticmethod(lambda **kw: recorded.append(kw))}))
    set_active_locale(lang)
    phone = _ListPhone((FIXTURES / name).read_text(encoding="utf-8"))
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    bundle.unfollow.active_account_id = 1
    return bundle, phone, recorded


def _the_view_is_seen_then_the_phone_stops(bundle, phone):
    """The category's view is seen loaded (a row offering to follow back), then the phone stops
    answering: its rows cannot be read."""
    seen = bundle.unfollow._has_follow_back_row

    def seen_then_stops():
        answer = seen()
        phone.stopped = True
        return answer

    bundle.unfollow._has_follow_back_row = seen_then_stops


@pytest.mark.parametrize("name,lang,fans", SERVED, ids=["410 en", "447 fr"])
def test_the_fans_on_screen_are_read_and_recorded(name, lang, fans, monkeypatch):
    bundle, _phone, recorded = _unfollow_on(name, lang, monkeypatch)

    stats = bundle.unfollow.scrape_non_followers_category()

    assert stats["success"] is True, stats
    assert stats["fans_count"] == len(fans) and stats["non_followers_count"] == len(fans)
    assert [row["username"] for row in recorded] == fans


@pytest.mark.parametrize("name,lang,fans", SERVED, ids=["410 en", "447 fr"])
def test_a_category_whose_rows_cannot_be_read_is_a_failed_read(name, lang, fans, monkeypatch):
    bundle, phone, recorded = _unfollow_on(name, lang, monkeypatch)
    _the_view_is_seen_then_the_phone_stops(bundle, phone)

    stats = bundle.unfollow.scrape_non_followers_category()

    assert stats["success"] is False
    assert stats.get("read_failed") is True
    assert stats["fans_count"] is None and stats["non_followers_count"] is None, "a failed read passed for a count"
    assert recorded == []


def _after(bundle, name, then):
    """`bundle.unfollow.<name>` answers as in production, then `then()` changes the phone."""
    real = getattr(bundle.unfollow, name)

    def answered_then(*args, **kwargs):
        answer = real(*args, **kwargs)
        then()
        return answer

    setattr(bundle.unfollow, name, answered_then)


def _assert_failed_read(stats, recorded):
    assert stats["success"] is False
    assert stats.get("read_failed") is True
    assert stats["fans_count"] is None and stats["non_followers_count"] is None, "a failed read passed for a count"
    assert recorded == []


def test_a_screen_unread_after_a_scroll_fails_the_whole_read(monkeypatch):
    # The first screen gives its fans; after the scroll the phone stops answering: a list read in
    # part is no list of the fans (it used to end there, as if the list had).
    name, lang, _fans = SERVED[0]
    bundle, phone, recorded = _unfollow_on(name, lang, monkeypatch)
    _after(bundle, "_scroll_following_list", lambda: setattr(phone, "stopped", True))

    _assert_failed_read(bundle.unfollow.scrape_non_followers_category(), recorded)


def test_a_first_screen_without_a_fan_fails_the_read(monkeypatch):
    # The category's view was seen (a row offering to follow back), then the read finds another list
    # (another account's followers, 410 in English, no row offering to follow back): that is no
    # empty category.
    name, lang, _fans = SERVED[0]
    bundle, phone, recorded = _unfollow_on(name, lang, monkeypatch)
    other_list = (FIXTURES / "ig410_en_followers_list_of_another_account.xml").read_text(encoding="utf-8")
    _after(bundle, "_has_follow_back_row", lambda: setattr(phone, "xml", other_list))

    _assert_failed_read(bundle.unfollow.scrape_non_followers_category(), recorded)


def test_rows_offering_to_follow_back_without_a_name_fail_the_read(monkeypatch):
    # After the scroll, rows offer to follow back and none of their names can be read. Derived from
    # the real capture: the same screen, its usernames emptied.
    name, lang, fans = SERVED[0]
    bundle, phone, recorded = _unfollow_on(name, lang, monkeypatch)
    nameless = phone.xml
    for fan in fans:
        nameless = nameless.replace(f'text="{fan}"', 'text=""')
    assert nameless != phone.xml
    _after(bundle, "_scroll_following_list", lambda: setattr(phone, "xml", nameless))

    _assert_failed_read(bundle.unfollow.scrape_non_followers_category(), recorded)


def _runner_on(business):
    from types import SimpleNamespace

    from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner

    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = SimpleNamespace()
    runner.logger = logger
    runner._get_unfollow_business = lambda: business
    return runner


def _sync_complete(out):
    import json

    (line,) = [json.loads(text) for text in out.splitlines()
               if text.startswith("{") and json.loads(text).get("type") == "sync_complete"]
    return line


def test_the_sync_line_says_null_for_a_fans_category_not_read(monkeypatch, capsys):
    # The following sync then the fans category, whose rows cannot be read: the line the app shows
    # says null, never 0. The following list's own read is not this test's subject.
    name, lang, _fans = SERVED[0]
    bundle, phone, _recorded = _unfollow_on(name, lang, monkeypatch)
    _the_view_is_seen_then_the_phone_stops(bundle, phone)
    bundle.unfollow.sync_following_list = lambda *a, **k: {
        "new_count": 0, "updated_count": 0, "stopped_early": False, "success": True}

    _runner_on(bundle.unfollow)._run_sync_following_workflow({"type": "sync_following"})

    line = _sync_complete(capsys.readouterr().out)
    assert line["non_followers_count"] is None and line["success"] is False


def test_the_followers_and_following_sync_does_not_announce_fans_it_never_read(capsys):
    from types import SimpleNamespace

    lists = {"new_count": 1, "updated_count": 2, "total_seen": 3, "stopped_early": False, "success": True}
    business = SimpleNamespace(
        sync_following_list=lambda *a, **k: dict(lists),
        sync_followers_list=lambda *a, **k: dict(lists),
        device=SimpleNamespace(device=SimpleNamespace(press=lambda *_a: True)),
    )

    _runner_on(business)._run_sync_followers_following_workflow({"type": "sync_followers_following"})

    assert _sync_complete(capsys.readouterr().out)["non_followers_count"] is None


def test_the_lab_says_the_fans_were_not_read_never_zero(monkeypatch):
    name, lang, _fans = SERVED[0]
    bundle, phone, _recorded = _unfollow_on(name, lang, monkeypatch)
    _the_view_is_seen_then_the_phone_stops(bundle, phone)

    result = INSTAGRAM_ACTIONS["unfollow.read_fans_category"](bundle, {})

    assert result["success"] is False
    assert "0 fans" not in result["message"], result["message"]
    assert result["details"]["read_failed"] is True
