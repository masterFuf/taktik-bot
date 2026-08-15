"""Characterisation tests for the direct followers loop.

`interact_with_followers_direct` carries nineteen commits of production fixes and had no
test covering the loop itself. Each fix answers a failure seen on a real device, and each
lives as a counter or a flag inside a 500-line function — the exact shape where a refactor
silently loses one and nobody notices until a run behaves oddly forty minutes in.

These tests pin the BEHAVIOUR, not the structure: they drive the real mixin through a
scripted fake device and assert what the run produced. They are written to survive the
extraction work that follows — if a split breaks one of them, it broke a fix.

Each test names the failure it guards. The scenarios come from the commit history:
  - false end-of-list that cut runs at 24/472
  - back-at-top-of-list handled as scroll-past, not as a session stop
  - lost navigation ending the WHOLE run instead of blind-scrolling a dead screen
  - a head of list served full of private profiles
  - "already known" kept out of the rejection buckets
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.main_loop import (
    FollowerDirectWorkflowMixin,
)
import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.main_loop as main_loop


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def success(self, *a, **k): pass


class _Tracker:
    """Stands in for FollowersTracker, which otherwise writes a log file per run."""

    def __init__(self, *a, **k):
        self.loop_on_scan = []
        self.scrolls = []

    def get_log_file_path(self): return "(test)"
    def log_visible_followers(self, usernames, kind):
        return self.loop_on_scan.pop(0) if self.loop_on_scan else False
    def log_position_check(self, *a, **k): pass
    def check_position_after_back(self, *a, **k): return True
    def log_skipped_from_db(self, *a, **k): pass
    def log_scroll(self, kind): self.scrolls.append(kind)
    def log_session_end(self, stats): pass


class _ScrollDetector:
    """Records what the loop feeds it — that gating IS the 24/472 fix."""

    instances = []

    def __init__(self, repeats_to_end=5, device=None):
        self.notified = []
        _ScrollDetector.instances.append(self)

    def notify_new_page(self, visible, processed):
        self.notified.append(list(visible))


class _Helpers:
    def __init__(self):
        self.finalized = []

    def finalize_session(self, status, reason):
        self.finalized.append((status, reason))


class _Automation:
    def __init__(self, username="me"):
        self.active_username = username
        self.helpers = _Helpers()


class _Actions:
    """A screen that only changes when something scrolls it.

    This is the point of the fake: the loop deliberately re-scans the SAME page after each
    profile (process one -> break -> re-scan), so a page must keep being served until a
    scroll happens. A fake that hands out the next page on every read would hide exactly
    the re-scan behaviour these tests exist to pin.
    """

    def __init__(self, pages):
        self.pages = list(pages) or [[]]
        self.index = 0
        self.scrolls = 0
        self.load_more_calls = 0

    def get_visible_followers_with_elements(self):
        page = self.pages[self.index] if self.index < len(self.pages) else []
        return [{'username': u, 'element': object()} for u in page]

    def scroll_followers_list_down(self):
        self.scrolls += 1
        if self.index < len(self.pages) - 1:
            self.index += 1

    def check_and_click_load_more(self):
        self.load_more_calls += 1
        return None


class _StatsManager:
    def display_stats(self, **k): pass
    def display_final_stats(self, **k): pass


class Runner(FollowerDirectWorkflowMixin):
    """The REAL mixin, with every collaborator faked out."""

    def __init__(self, pages, *, followers_count=100, process_results=None,
                 ensure_back=True, private_flags=None, loop_on_scan=None):
        self.logger = _Logger()
        self.device = object()
        self.session_manager = None
        self.automation = _Automation()
        self.detection_actions = _Actions(pages)
        self.scroll_actions = self.detection_actions
        self.stats_manager = _StatsManager()
        self._followers_count = followers_count
        self._process_results = list(process_results or [])
        self._ensure_back = ensure_back
        self._private_flags = list(private_flags or [])
        self._last_visit_was_private = None
        self._loop_on_scan = list(loop_on_scan or [])
        self.processed_calls = []
        self.escaped = 0
        self.empty_screen_calls = 0

    # -- collaborators the loop calls, all stubbed to a scripted outcome ------
    def _maybe_take_break(self): return False
    def _recover_after_break(self, *a, **k): pass
    def _human_like_delay(self, *a, **k): pass

    def _setup_direct_workflow(self, target_username, stats, config, deep_link, force_search):
        return self._followers_count, {}

    def _handle_empty_followers_screen(self, detector):
        self.empty_screen_calls += 1
        return False

    def _process_single_follower_direct(self, username, idx, stats, cfg, account_id,
                                        target, target_count, seen, max_interactions, tracker):
        self.processed_calls.append(username)
        self._last_visit_was_private = (
            self._private_flags.pop(0) if self._private_flags else None
        )
        outcome = self._process_results.pop(0) if self._process_results else True
        if outcome is True:
            stats['interacted'] += 1
        return outcome

    def _ensure_on_followers_list(self, target, force_back=False):
        return self._ensure_back

    def _escape_private_zone(self, policy, jumps, followers_count):
        self.escaped += 1
        return 3

    def _record_restriction_signal(self, **k): pass

    def _handle_scroll_and_end_detection(self, *a, **k):
        return False, None


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """No log file, no stdout JSON, no DB — the loop is what is under test."""
    _ScrollDetector.instances.clear()
    monkeypatch.setattr(main_loop, "FollowersTracker", _Tracker)
    monkeypatch.setattr(main_loop, "ScrollEndDetector", _ScrollDetector)
    monkeypatch.setattr(main_loop.IPCEmitter, "emit_profile_skipped", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(main_loop.IPCEmitter, "emit_action", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(main_loop, "emit_step", lambda *a, **k: None)


def test_a_plain_run_interacts_with_every_visible_follower():
    runner = Runner(pages=[["alice", "bob", "carol"], []])
    stats = runner.interact_with_followers_direct("target", max_interactions=3)

    assert runner.processed_calls == ["alice", "bob", "carol"]
    assert stats['interacted'] == 3
    assert stats['stop_reason'] == ''


def test_the_budget_is_a_hard_stop():
    runner = Runner(pages=[["a", "b", "c", "d", "e"]])
    stats = runner.interact_with_followers_direct("target", max_interactions=2)

    assert stats['interacted'] == 2
    assert len(runner.processed_calls) == 2


def test_a_page_still_being_worked_is_not_reported_as_a_duplicate():
    """The false end-of-list that stopped runs at 24/472.

    The loop processes ONE follower then re-scans the same page. Feeding those identical
    re-scans to the end-of-scroll detector inflated its duplicate-page counter and tripped
    a false end of list. It must only be notified once the page holds nothing new.
    """
    runner = Runner(pages=[["alice", "bob", "carol"], []])
    runner.interact_with_followers_direct("target", max_interactions=3)

    detector = _ScrollDetector.instances[0]
    # Three re-scans of a page with fresh followers must produce NO duplicate signal.
    assert detector.notified == [], (
        "the detector was told about a page that was still being worked through"
    )


def test_landing_back_on_top_scrolls_past_instead_of_ending_the_run(monkeypatch):
    """A back/recovery landing at the top of the list is not a reason to stop.

    The right move is to scroll PAST the already-seen region and resume discovery. Only a
    list genuinely stuck at the top (scrolling never advances) ends the run.
    """
    class _LoopingTracker(_Tracker):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.calls = 0

        def log_visible_followers(self, usernames, kind):
            self.calls += 1
            return self.calls == 1  # top-of-list detected once, then normal

    monkeypatch.setattr(main_loop, "FollowersTracker", _LoopingTracker)
    # Three scroll-pasts land further down the list, where a fresh follower waits.
    runner = Runner(pages=[["alice"], ["alice"], ["alice"], ["bob"], []])
    stats = runner.interact_with_followers_direct("target", max_interactions=1)

    assert runner.detection_actions.scrolls >= 3, "did not scroll past the seen region"
    assert stats['interacted'] == 1, "gave up instead of resuming discovery"
    assert stats['stop_reason'] == ''


def test_an_empty_list_ends_the_run_instead_of_scrolling_into_the_void():
    """Four consecutive empty scans mean the list is gone — stop, do not blind-scroll."""
    runner = Runner(pages=[[]])
    stats = runner.interact_with_followers_direct("target", max_interactions=10)

    assert stats['stop_reason'] == 'followers_list_unavailable'
    assert runner.empty_screen_calls == 3, "stopped on the 4th empty scan, not later"


def test_lost_navigation_ends_the_whole_run_not_just_the_inner_loop():
    """The fix behind '~7 min of empty scrolls': the flag must break the WHILE too."""
    runner = Runner(pages=[["alice", "bob", "carol"]], process_results=[None])
    stats = runner.interact_with_followers_direct("target", max_interactions=5)

    assert stats['stop_reason'] == 'navigation_lost'
    assert len(runner.processed_calls) == 1, "kept going after navigation was lost"
    assert runner.detection_actions.scrolls == 0, "scrolled a screen it could not identify"


def test_failing_to_return_to_the_list_also_ends_the_run():
    runner = Runner(pages=[["alice", "bob"]], ensure_back=False)
    stats = runner.interact_with_followers_direct("target", max_interactions=5)

    assert stats['stop_reason'] == 'navigation_lost'
    assert len(runner.processed_calls) == 1


def test_a_degraded_run_is_finalised_as_interrupted():
    """A run that died on lost navigation is not a completed run."""
    runner = Runner(pages=[["alice"]], process_results=[None])
    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert runner.automation.helpers.finalized == [("INTERRUPTED", "navigation_lost")]


def test_a_healthy_run_is_finalised_as_completed():
    runner = Runner(pages=[["alice"], []])
    runner.interact_with_followers_direct("target", max_interactions=1, finalize=True)

    status, _ = runner.automation.helpers.finalized[0]
    assert status == "COMPLETED"


def test_a_driver_run_does_not_finalise_the_session_itself():
    """finalize=False: a multi-target run finalises once, at the driver level."""
    runner = Runner(pages=[["alice"], []])
    runner.interact_with_followers_direct("target", max_interactions=1, finalize=False)

    assert runner.automation.helpers.finalized == []


def test_the_own_account_is_never_interacted_with():
    runner = Runner(pages=[["me", "alice"], []])
    runner.interact_with_followers_direct("target", max_interactions=5)

    assert "me" not in runner.processed_calls
    assert "alice" in runner.processed_calls


def test_the_target_account_is_never_interacted_with():
    runner = Runner(pages=[["target", "alice"], []])
    runner.interact_with_followers_direct("target", max_interactions=5)

    assert "target" not in runner.processed_calls


def test_a_private_streak_triggers_the_zone_escape(monkeypatch):
    """A run of private profiles means a served head of list, not a private source."""
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5", "p6"]],
        process_results=[False] * 6,
        private_flags=[True] * 6,
    )
    runner.interact_with_followers_direct("target", max_interactions=10)

    assert runner.escaped >= 1, "stayed in a zone it was supposed to transport past"


def test_an_allowed_private_profile_never_triggers_an_escape():
    """Nothing is being rejected, so there is no zone to leave.

    The policy disarms on `allow_private` — jumping would only skip valid targets.
    """
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5", "p6"], []],
        private_flags=[True] * 6,
    )
    runner.interact_with_followers_direct(
        "target", max_interactions=10,
        config={'filters': {'allow_private': True}},
    )

    assert runner.escaped == 0


def test_already_known_profiles_stay_out_of_the_rejection_buckets(monkeypatch):
    """'Already done' must never be tallied as 'rejected' — it inflates the run's stats."""
    monkeypatch.setattr(
        main_loop.InstagramWorkflowStateService, "is_profile_skippable",
        staticmethod(lambda username, account_id, **k: (True, "already_processed")),
    )
    monkeypatch.setattr(
        main_loop.InstagramWorkflowStateService, "get_skip_detail",
        staticmethod(lambda *a, **k: ""),
    )
    runner = Runner(pages=[["alice", "bob"], []])
    stats = runner.interact_with_followers_direct("target", max_interactions=5, account_id=7)

    assert stats['already_processed'] == 2
    assert stats['skipped'] == 0
    assert stats['filtered'] == 0
    assert runner.processed_calls == [], "opened a profile it already knew"
