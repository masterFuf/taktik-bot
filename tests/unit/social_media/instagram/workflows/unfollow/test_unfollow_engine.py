"""U1: one engine, fed with the whole page setting, deciding on data and checking on screen."""

from types import SimpleNamespace

import pytest

from fake_follow_list import (
    FakeDetection, FakeFacade, FakeScreen, follow_list_xml, profile_xml, walk_list,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.core.config_builder import build_instagram_automation_config
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    for module in (unfollow_workflow.time,):
        monkeypatch.setattr(module, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "profile_open_timeout", 0.0)
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_unfollow", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_stats", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(unfollow_workflow.IPCEmitter, "emit_unfollow_plan", staticmethod(lambda *a, **k: None))
    yield
    set_active_locale(None)


def _business(*screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    recorded = []
    business._record_action = lambda username, action, count=1: recorded.append(username)
    business._scroll_following_list = lambda: None
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    return business, screen, recorded


# ── The runner hands everything to the engine ──────────────────────────────────

def test_every_unfollow_field_of_the_page_reaches_the_engine(monkeypatch):
    page = {"maxUnfollows": 7, "unfollowMode": "mutual", "skipVerified": False, "skipBusiness": True,
            "minDaysSinceFollow": 9, "botFollowsOnly": False, "whitelist": ["keep_me"],
            "blacklist": ["drop_me"], "minDelay": 3, "maxDelay": 6}
    built = build_instagram_automation_config({"deviceId": "x", "workflowType": "unfollow", "unfollow": page,
                                               "session": {"durationMinutes": 30}})
    action = next(step for step in built["actions"] if step["type"] == "unfollow")

    seen = []
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = SimpleNamespace(stats={}, session_finalized=False, session_manager=None,
                                        helpers=SimpleNamespace(finalize_session=lambda **k: None))
    runner.logger = unfollow_workflow.logger
    engine = SimpleNamespace(run_unfollow_workflow=lambda cfg: seen.append(cfg) or {"unfollows_made": 1})
    monkeypatch.setattr(runner, "_get_unfollow_business", lambda: engine, raising=False)

    assert runner._run_unfollow_workflow(action) is True
    assert seen == [{
        "max_unfollows": 7, "unfollow_mode": "mutual", "unfollow_delay_range": (3.0, 6.0),
        "skip_verified": False, "skip_business": True, "min_days_since_follow": 9,
        "bot_follows_only": False, "whitelist": ["keep_me"], "blacklist": ["drop_me"],
    }]


def test_bot_follows_only_is_on_when_the_page_says_nothing():
    built = build_instagram_automation_config({"deviceId": "x", "workflowType": "unfollow", "unfollow": {},
                                               "session": {"durationMinutes": 30}})
    action = next(step for step in built["actions"] if step["type"] == "unfollow")
    assert action["bot_follows_only"] is True
    assert WorkflowRunner._unfollow_engine_config({}, 5)["bot_follows_only"] is True


def test_the_runner_keeps_one_engine_for_the_session():
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.automation = SimpleNamespace(device=FakeFacade(FakeScreen(follow_list_xml([]))),
                                        session_manager=None)
    first = runner._get_unfollow_business()
    assert runner._get_unfollow_business() is first


# ── The walk ───────────────────────────────────────────────────────────────────

def test_the_maximum_stops_the_walk_with_rows_left():
    before = follow_list_xml([("a1", "Suivi(e)"), ("a2", "Suivi(e)"), ("a3", "Suivi(e)")])
    after1 = follow_list_xml([("a1", "Suivre"), ("a2", "Suivi(e)"), ("a3", "Suivi(e)")])
    after2 = follow_list_xml([("a1", "Suivre"), ("a2", "Suivre"), ("a3", "Suivi(e)")])
    business, screen, recorded = _business(before, after1, after2)
    stats = walk_list(business, {"max_unfollows": 2})
    assert stats["unfollows_made"] == 2 and recorded == ["a1", "a2"]
    assert len(screen.taps) == 2


def test_three_unconfirmed_in_a_row_stop_the_run():
    stuck = follow_list_xml([(f"u{i}", "Suivi(e)") for i in range(6)])
    business, screen, recorded = _business(stuck)
    stats = walk_list(business, {"max_unfollows": 10})
    assert stats["unconfirmed"] == 3 and recorded == []
    assert stats["stop_reason"].code == "unfollow_unconfirmed"
    assert len(screen.taps) == 3


def test_a_later_batch_never_taps_again_what_an_earlier_one_handled():
    stuck = follow_list_xml([("sticky", "Suivi(e)")])
    business, screen, _recorded = _business(stuck)
    walk_list(business, {"max_unfollows": 5})
    walk_list(business, {"max_unfollows": 5})
    assert len(screen.taps) == 1


# ── The whole engine, non-followers mode ───────────────────────────────────────

def test_non_followers_run_decides_on_data_and_checks_the_badge(monkeypatch):
    rows = follow_list_xml([("ghost", "Suivi(e)"), ("hidden_fan", "Suivi(e)"), ("friend", "Suivi(e)")])
    screens = [
        rows,
        profile_xml("ghost", follows_you=False),       # its profile, opened from the row
        rows,                                           # back to the list
        follow_list_xml([("ghost", "Suivre"), ("hidden_fan", "Suivi(e)"), ("friend", "Suivi(e)")]),
        profile_xml("hidden_fan", follows_you=True),    # the badge the followers sync missed
        rows,
    ]
    business, screen, recorded = _business(*screens)
    business.detection_actions = FakeDetection(screen, business)
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_following_list = lambda: True
    business.sync_following_list = lambda cfg: {"complete": True}
    # the followers sync saw nobody of the three, and read the whole list
    business.sync_followers_list = lambda cfg: {"usernames": {"someone_else"}, "complete": True}
    monkeypatch.setattr(unfollow_workflow.InstagramFollowGraphService, "list_active_followings",
                        staticmethod(lambda account_id: [
                            {"username": "ghost", "last_bot_follow_at": "2026-09-01T10:00:00", "first_seen_at": None},
                            {"username": "hidden_fan", "last_bot_follow_at": "2026-09-02T10:00:00", "first_seen_at": None},
                            {"username": "friend", "last_bot_follow_at": None, "first_seen_at": "2026-01-01 00:00:00"},
                        ]))

    stats = business.run_unfollow_workflow({"unfollow_mode": "non-followers", "max_unfollows": 5,
                                            "min_days_since_follow": 3})

    assert recorded == ["ghost"]
    assert stats["unfollows_made"] == 1
    assert stats["candidates"] == 2 and stats["refusals"] == {"not_followed_by_bot": 1}
    assert stats["profile_refusals"] == {"follows_back": 1}
    # Back from each profile with the key the device obeys, never the Instagram facade's
    # press('back'), which uiautomator2 ignores (C2, 2026-09-23).
    assert screen.presses == ["back", "back"]


def test_back_from_a_profile_reaches_the_list_with_a_key_the_device_obeys():
    rows = follow_list_xml([("ghost", "Suivi(e)")])
    business, screen, _recorded = _business(profile_xml("ghost"), rows)
    business.detection_actions = FakeDetection(screen, business)

    business._go_back_to_following_list()

    assert business.detection_actions.is_following_list_open()
    assert screen.presses == ["back"]


def test_the_instagram_facade_press_back_is_ignored_by_the_device():
    # Documents the facade defect the engine works around: press('back') becomes "KEYCODE_BACK",
    # a key name the uiautomator2 server does not know. To fix in the facade itself (report).
    business, screen, _recorded = _business(profile_xml("ghost"), follow_list_xml([]))
    business.device.press("back")
    assert screen.presses == ["KEYCODE_BACK"] and screen.index == 0


def test_an_incomplete_followers_sync_unfollows_nobody_in_non_followers_mode(monkeypatch):
    business, screen, recorded = _business(follow_list_xml([("ghost", "Suivi(e)")]))
    business._get_account_id = lambda: 1
    business.sync_following_list = lambda cfg: {}
    business.sync_followers_list = lambda cfg: {"usernames": set(), "complete": False}
    monkeypatch.setattr(unfollow_workflow.InstagramFollowGraphService, "list_active_followings",
                        staticmethod(lambda account_id: [
                            {"username": "ghost", "last_bot_follow_at": "2026-09-01T10:00:00", "first_seen_at": None}]))

    stats = business.run_unfollow_workflow({"unfollow_mode": "non-followers", "max_unfollows": 5})

    assert stats["candidates"] == 0 and stats["refusals"] == {"reciprocity_unknown": 1}
    assert screen.taps == [] and recorded == []
