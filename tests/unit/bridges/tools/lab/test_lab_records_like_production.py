"""What the Lab does on the phone is written in the base the way a run writes it.

Pixel 6a, Instagram 447, 2026-10-24 (P12): `engagement.engage_likers` gave three real likes, and
the base got none of them. The log said « Database service not configured », « account_id
missing - cannot mark @... as processed » and « Cannot record LIKE - no account_id ». Two holes:

- the Lab opened the bot's base only to resolve its `account` parameter: an action run without it
  drove production code that reads and writes the base, with no base open;
- the bundle built its production classes without the `automation` a run gives them, the object
  every one of them, and every business they build in turn (the feed's `like_business`, which
  records the likes of the likers loop), asks for the account and the session. Binding the account
  set it on the six components of the bundle, not on the businesses inside them.
"""

from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.action_test import runner
from bridges.tools.lab.action_test.action_bundle import open_bot_base, resolve_lab_account_id
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.tools.lab.action_test.tracing import SelectorTracer
from unit.paths import CORE


# A real screen, none of whose rows the tests here read: the bundle only needs one to be built.
SCREEN = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_own_followers_list_deactivated_category.xml"
          ).read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the bundle touches it: one screen, nothing tapped."""

    wait_timeout = 0.2

    def __init__(self):
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREEN

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2220)


def _bundle():
    return build_instagram_action_bundle(create_instagram_device_facade(_Phone()))


def test_the_lab_opens_the_bot_base_before_the_action(lab_base, monkeypatch):
    """An action run without the `account` parameter, as `engagement.engage_likers` was."""
    from taktik.core.database import get_db_service

    seen = []
    monkeypatch.setattr(runner, "emit", lambda payload: seen.append(payload))
    runner._execute_action({"engagement.probe": lambda a, p: seen.append(get_db_service()) or True},
                           "engagement.probe", _bundle(), {}, SelectorTracer(), exit_on_error=False)

    assert seen[0] is not None and seen[-1]["success"] is True
    assert lab_base.exists()


def test_the_bound_account_reaches_the_businesses_built_inside_the_bundle(lab_base):
    bundle = _bundle()
    bundle.bind_account(42)

    for business in (bundle.feed.like_business, bundle.feed.comment_business, bundle.feed.story_business,
                     bundle.like, bundle.comment, bundle.story, bundle.feed, bundle.unfollow, bundle.popup):
        assert business._get_account_id() == 42


def test_a_like_of_the_likers_loop_is_recorded_under_the_bound_account(lab_base):
    """The write the likers loop makes after its likes (`LikeOrchestration.like_profile_posts`
    through the feed's `like_business`): refused before, « Cannot record LIKE - no account_id »."""
    import sqlite3

    open_bot_base()
    bundle = _bundle()
    account_id = resolve_lab_account_id({"account": "lab_tester"})
    bundle.bind_account(account_id)

    assert bundle.feed.like_business._record_action("liker_one", "LIKE") is True
    with sqlite3.connect(lab_base) as base:
        rows = base.execute("SELECT interaction_type FROM interactions WHERE account_id = ?", (account_id,)).fetchall()
    assert rows == [("LIKE",)]


def test_without_an_account_nothing_is_written_and_it_is_said(lab_base):
    bundle = _bundle()
    bundle.bind_account(None)

    assert bundle.feed.like_business._get_account_id() is None
    assert bundle.feed.like_business._record_action("liker_one", "LIKE") is False


def _likers_run(monkeypatch, params):
    """`engagement.engage_likers` through the runner, its loop replaced by a witness of the account
    the feed's like business would record under."""
    from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    bundle = _bundle()
    walked = []
    monkeypatch.setattr(bundle.feed, "_interact_with_likers_list",
                        lambda **kw: walked.append(bundle.feed.like_business._get_account_id()))
    emitted = []
    monkeypatch.setattr(runner, "emit", emitted.append)
    runner._execute_action(ACTION_REGISTRY, "engagement.engage_likers", bundle, params, SelectorTracer(),
                           exit_on_error=False)
    return walked, emitted[-1]


def test_the_likers_loop_runs_under_the_account_it_records_for(lab_base, monkeypatch):
    walked, _result = _likers_run(monkeypatch, {"account": "lab_tester", "max_interactions": 1})
    assert len(walked) == 1 and walked[0] is not None


def test_the_likers_loop_without_an_account_touches_nothing(lab_base, monkeypatch):
    walked, result = _likers_run(monkeypatch, {"max_interactions": 1})
    assert walked == []
    assert result["success"] is False
    assert "account param is required" in result["message"]
