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
# The "already known" decision lives with the profile-processing mixin, so its collaborators
# (database service, IPC) are patched there rather than on the loop module.
import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.profile_processing as profile_processing
# The transport out of a private zone lives with the navigation mixin, and emits from there.
import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.navigation_helpers as navigation_helpers


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

    #: The real `_handle_empty_followers_screen` asks the detector twice before concluding.
    #: Neutral by default: no button to click, not the end.
    def click_load_more_if_present(self): return False
    def is_the_end(self): return False


class _Helpers:
    def __init__(self):
        self.finalized = []

    def finalize_session(self, status, reason):
        self.finalized.append((status, reason))


class _RestartableHelpers(_Helpers):
    def _get_package(self): return "com.instagram.android"


class _DeviceManager:
    def __init__(self): self.launches = []
    def launch_app(self, package, stop_first=False):
        self.launches.append((package, stop_first))
        return True


class _Automation:
    """Restarting the app is opt-in.

    A run can only relaunch when the automation exposes both a device manager and the package
    name; without them the loop stops on a lost navigation exactly as it did before. Keeping
    that the DEFAULT here is what lets the older tests go on pinning "a lost navigation ends the
    run" — which is still true whenever the relaunch is unavailable or fails.
    """

    def __init__(self, username="me", restartable=False):
        self.active_username = username
        self.helpers = _RestartableHelpers() if restartable else _Helpers()
        self.device_manager = _DeviceManager() if restartable else None


class _Actions:
    """A screen that only changes when something scrolls it.

    This is the point of the fake: the loop deliberately re-scans the SAME page after each
    profile (process one -> break -> re-scan), so a page must keep being served until a
    scroll happens. A fake that hands out the next page on every read would hide exactly
    the re-scan behaviour these tests exist to pin.
    """

    def __init__(self, pages, trace=None):
        self.pages = list(pages) or [[]]
        self.suggestions_on_pages = set()
        self.index = 0
        self.scrolls = 0
        self.load_more_calls = 0
        #: Ordered log of what the loop did — 'scan' / 'scroll' / 'escape'. Some fixes are
        #: about the ORDER of two actions, which a counter cannot express.
        self.trace = trace if trace is not None else []

    def get_visible_followers_with_elements(self):
        self.trace.append('scan')
        page = self.pages[self.index] if self.index < len(self.pages) else []
        return [{'username': u, 'element': object()} for u in page]

    def scroll_followers_list_down(self):
        self.scrolls += 1
        self.trace.append('scroll')
        if self.index < len(self.pages) - 1:
            self.index += 1

    def check_and_click_load_more(self):
        self.load_more_calls += 1
        return None

    def is_in_suggestions_section(self):
        """True once the list has run past its real followers, per page index."""
        return self.index in self.suggestions_on_pages


class _StatsManager:
    def display_stats(self, **k): pass
    def display_final_stats(self, **k): pass


class Runner(FollowerDirectWorkflowMixin):
    """The REAL mixin, with every collaborator faked out."""

    def __init__(self, pages, *, followers_count=100, process_results=None,
                 ensure_back=True, private_flags=None, loop_on_scan=None,
                 real_empty_screen_handler=False, end_detection_results=None,
                 restartable=False):
        self.logger = _Logger()
        self.device = object()
        self.session_manager = None
        self.automation = _Automation(restartable=restartable)
        self.trace = []
        self.detection_actions = _Actions(pages, trace=self.trace)
        self.scroll_actions = self.detection_actions
        self.stats_manager = _StatsManager()
        self._followers_count = followers_count
        self._process_results = list(process_results or [])
        self._ensure_back = ensure_back
        self._private_flags = list(private_flags or [])
        self._last_visit_was_private = None
        self._loop_on_scan = list(loop_on_scan or [])
        self._real_empty_screen_handler = real_empty_screen_handler
        self._end_detection_results = list(end_detection_results or [])
        self.recorded_signals = []
        self.processed_calls = []
        self.escaped = 0
        self.empty_screen_calls = 0
        self.end_detection_args = ()

    # -- collaborators the loop calls, all stubbed to a scripted outcome ------
    def _maybe_take_break(self): return False
    def _recover_after_break(self, *a, **k): pass
    def _human_like_delay(self, *a, **k): pass

    def _setup_direct_workflow(self, target_username, stats, config, deep_link, force_search):
        return self._followers_count, {}

    def _handle_empty_followers_screen(self, detector, total_usernames_seen=0):
        self.empty_screen_calls += 1
        if self._real_empty_screen_handler:
            return super()._handle_empty_followers_screen(detector, total_usernames_seen)
        return None

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
        """A real transport FLINGS the list, so the fake must move it too.

        Without this the run lands back on the page it just left, every counter the escape
        resets stays irrelevant, and the tests cannot see what the block left behind.
        """
        self.escaped += 1
        self.trace.append('escape')
        actions = self.detection_actions
        if actions.index < len(actions.pages) - 1:
            actions.index += 1
        return 3

    def _record_restriction_signal(self, **k): self.recorded_signals.append(k)

    def _handle_scroll_and_end_detection(self, *a, **k):
        self.end_detection_args = a
        # Position 11 is known_usernames_streak, the two last are the operator limits.
        self.trace.append(('end_check', a[11]))
        if self._end_detection_results:
            return self._end_detection_results.pop(0)
        return False, None


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    """No log file, no stdout JSON, no DB — the loop is what is under test."""
    _ScrollDetector.instances.clear()
    monkeypatch.setattr(main_loop, "FollowersTracker", _Tracker)
    monkeypatch.setattr(main_loop, "ScrollEndDetector", _ScrollDetector)
    monkeypatch.setattr(main_loop.IPCEmitter, "emit_action", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(profile_processing.IPCEmitter, "emit_profile_skipped",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(main_loop, "emit_step", lambda *a, **k: None)
    monkeypatch.setattr(profile_processing, "emit_step", lambda *a, **k: None)
    monkeypatch.setattr(navigation_helpers, "emit_step", lambda *a, **k: None)
    # No test may ever wait on the wall clock. The safety net for a slow list is the only
    # code here that sleeps; tests that care about it re-patch this with `_sleepless`.
    monkeypatch.setattr(navigation_helpers.time, "sleep", lambda seconds: None)


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


def test_scattered_empty_scans_do_not_add_up_into_a_false_stop():
    """Only FOUR IN A ROW mean the list is gone.

    A single empty scan is ordinary — the list is still loading. If the counter never
    resets when followers come back, four scattered empties across a long run add up and
    kill a perfectly healthy session.
    """
    # Empty, then followers, four times over: four empties in total, never four in a row.
    # The budget stays above the number of profiles on purpose — a run that stopped on
    # "enough interactions" would never reach the fourth empty and prove nothing.
    # Ends on content, not on emptiness: a list that really goes quiet at the end SHOULD
    # stop the run, and that legitimate stop would mask what this test is looking for.
    runner = Runner(pages=[[], ["alice"], [], ["bob"], [], ["carol"], [], ["dave"]])
    stats = runner.interact_with_followers_direct("target", max_interactions=10)

    assert stats['stop_reason'] != 'followers_list_unavailable', (
        "scattered empty scans were counted as a run of four"
    )
    assert stats['interacted'] == 4


def test_scattered_returns_to_the_top_do_not_add_up_into_a_false_stop():
    """Only CONSECUTIVE re-tops end the run.

    A back or a recovery lands at the top of the list now and then over a long session.
    If the counter never clears on a normal scan, those scattered landings accumulate,
    reach the ceiling of eight, and stop a run that was working perfectly well.
    """
    class _AlternatingTracker(_Tracker):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.calls = 0

        def log_visible_followers(self, usernames, kind):
            self.calls += 1
            return self.calls % 2 == 1  # every other scan lands back at the top

    import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.main_loop as ml
    original = ml.FollowersTracker
    ml.FollowersTracker = _AlternatingTracker
    try:
        # Every re-top spends three scroll-pasts, so the list has to be long enough for the
        # run to still be working after more than eight scattered landings — a shorter one
        # would run dry before reaching the point being tested.
        runner = Runner(pages=[[f"user{i}"] for i in range(80)])
        stats = runner.interact_with_followers_direct("target", max_interactions=12)
    finally:
        ml.FollowersTracker = original

    assert stats['interacted'] == 12, (
        "scattered returns to the top were counted as a consecutive run of eight, "
        "so the session stopped while the list was still giving followers"
    )


def test_a_list_stuck_at_the_top_does_eventually_end_the_run():
    """The other side of the back-at-top fix: scrolling that never advances must stop.

    Without a ceiling the run flings at an unmoving list until the global scroll cap,
    which is minutes of non-human bursts for nothing.
    """
    class _AlwaysLooping(_Tracker):
        def log_visible_followers(self, usernames, kind):
            return True  # every scan lands back at the top

    import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.main_loop as ml
    original = ml.FollowersTracker
    ml.FollowersTracker = _AlwaysLooping
    try:
        runner = Runner(pages=[["alice"]])
        runner.interact_with_followers_direct("target", max_interactions=5)
    finally:
        ml.FollowersTracker = original

    # 8 detections x 3 scroll-pasts = 24 scrolls, then the run ends. The global cap is 100.
    assert runner.detection_actions.scrolls <= 30, (
        f"{runner.detection_actions.scrolls} scrolls on a list that never advances — "
        "the stuck-at-top ceiling is gone"
    )
    # And it says which ceiling it hit: a list that will not advance is a screen to go and
    # look at, not a run that did its job.
    status, reason = runner.automation.helpers.finalized[-1]
    assert getattr(reason, 'code', None) == 'stuck_at_top'
    assert status == "INTERRUPTED"


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


def test_the_escape_leaves_the_streak_clean_behind_it():
    """After transporting, the streak must restart from zero.

    Kept apart from "the escape fires" on purpose: a streak that survives its own rescue
    re-fires the escape on the very next scan, and the run spends its budget flinging
    instead of interacting. The page below is exhausted after the jump, so nothing else
    can reset the streak — only the escape itself can.
    """
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5"]],
        process_results=[False] * 5,
        private_flags=[True] * 5,
    )
    runner.interact_with_followers_direct("target", max_interactions=10)

    assert runner.escaped == 1, (
        f"transported {runner.escaped} times for one private zone — "
        "the streak or the jump counter did not survive the rescue"
    )


def test_the_number_of_jumps_is_bounded():
    """A source that stays private must not be flung through forever."""
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5"], ["q1", "q2", "q3", "q4", "q5"],
               ["r1", "r2", "r3", "r4", "r5"], ["s1", "s2", "s3", "s4", "s5"],
               ["t1", "t2", "t3", "t4", "t5"]],
        process_results=[False] * 25,
        private_flags=[True] * 25,
    )
    runner.interact_with_followers_direct("target", max_interactions=30)

    assert runner.escaped <= 3, (
        f"{runner.escaped} transports — the jump counter is not advancing, "
        "so max_jumps is never reached"
    )


def test_the_transport_goes_back_to_scanning_not_to_scrolling():
    """The escape ends with a rescan, never by falling through into the scroll code.

    Falling through would scroll straight after a fling — a second displacement the
    workflow never decided — and would feed the end-of-scroll detector a page it never
    really worked.
    """
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5"]],
        process_results=[False] * 5,
        private_flags=[True] * 5,
    )
    runner.interact_with_followers_direct("target", max_interactions=10)

    # What matters is the ORDER, not the count: whatever the loop does later, the action
    # right after a transport must be a rescan.
    after_escape = [runner.trace[i + 1]
                    for i, event in enumerate(runner.trace)
                    if event == 'escape' and i + 1 < len(runner.trace)]
    assert after_escape, "no transport happened, the scenario is not exercising the escape"
    assert set(after_escape) == {'scan'}, (
        f"after a transport the loop did {after_escape} — it fell through into the "
        "scroll code instead of rescanning where the fling landed"
    )


def test_a_fresh_end_of_scroll_detector_follows_the_jump():
    """A large jump looks exactly like reaching the bottom to a detector that kept its
    history, so the transport must hand the loop a new one."""
    runner = Runner(
        pages=[["p1", "p2", "p3", "p4", "p5"]],
        process_results=[False] * 5,
        private_flags=[True] * 5,
    )
    runner.interact_with_followers_direct("target", max_interactions=10)

    assert len(_ScrollDetector.instances) >= 2, (
        "the detector was not rebuilt after the transport — its pre-jump history "
        "would read the landing zone as the end of the list"
    )


def test_a_fling_that_outruns_the_loading_does_not_kill_the_run():
    """The empty-screen gate of the transport, in the exact case it exists for.

    A fling carries the list further than it can render, so the landing scan comes back
    empty. If the escape does not clear the empty-screen counter, those post-jump empties
    add to whatever came before and the rescue becomes what ends the run.
    """
    runner = Runner(
        # One private per page — the run scrolls between them, exactly as it does when a
        # source keeps serving private profiles. Then the landing zone is still loading.
        pages=[["p1"], ["p2"], ["p3"], ["p4"], ["p5"], [], ["alice", "bob"]],
        process_results=[False] * 5,
        private_flags=[True] * 5,
    )
    stats = runner.interact_with_followers_direct("target", max_interactions=2)

    assert runner.escaped == 1
    assert stats['stop_reason'] != 'followers_list_unavailable', (
        "the run died on the empty scans that followed its own transport"
    )
    assert stats['interacted'] == 2, "never reached the profiles past the private zone"


def test_the_landing_zone_is_not_read_as_a_loop():
    """The top-loop gate: the zone the fling landed on is unknown to the anti-loop check,
    so a detection right after a transport must not sit on a counter left near its ceiling.
    """
    state = {'runner': None, 'fired': False}

    class _LoopsAfterTransport(_Tracker):
        def log_visible_followers(self, usernames, kind):
            # Fire exactly once, on the first scan that follows the transport.
            runner = state['runner']
            if runner and runner.escaped and not state['fired']:
                state['fired'] = True
                return True
            return False

    import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.main_loop as ml
    original = ml.FollowersTracker
    ml.FollowersTracker = _LoopsAfterTransport
    try:
        runner = Runner(
            pages=[["p1"], ["p2"], ["p3"], ["p4"], ["p5"],
                   ["alice"], ["alice"], ["alice"], ["alice"]],
            process_results=[False] * 5,
            private_flags=[True] * 5,
        )
        state['runner'] = runner
        stats = runner.interact_with_followers_direct("target", max_interactions=1)
    finally:
        ml.FollowersTracker = original

    assert runner.escaped == 1
    assert state['fired'], "the loop detection never happened, nothing was exercised"
    assert stats['interacted'] == 1, (
        "a single loop detection after the transport ended the run — the top-loop "
        "counter was not cleared by the escape"
    )


def test_the_known_streak_restarts_after_a_transport():
    """The known-streak gate: landing in already-worked territory would trip the
    stop-this-source rule and cancel the benefit of the jump.

    The streak handed to the end-of-source rule right after a transport must be back to
    zero, whatever it was before the fling.
    """
    runner = Runner(
        pages=[["p1"], ["p2"], ["p3"], ["p4"], ["p5"], ["alice"], []],
        process_results=[False] * 5,
        private_flags=[True] * 5,
    )
    runner.interact_with_followers_direct(
        "target", max_interactions=1,
        config={'max_consecutive_known_usernames': 3},
    )

    assert runner.escaped == 1
    # The first end-of-source check AFTER the transport is the one that matters.
    after = runner.trace[runner.trace.index('escape'):]
    checks = [event[1] for event in after
              if isinstance(event, tuple) and event[0] == 'end_check']
    assert checks, "the end-of-source rule was never consulted after the transport"
    assert checks[0] == 0, (
        f"known streak was {checks[0]} on the first check after a transport — the escape "
        "left the run one step from stopping the source it had just rescued"
    )


def test_a_second_private_zone_is_still_escaped():
    """The jump counter must advance by ONE: too fast and the second real zone is refused.

    Two separate private zones, each deserving its own transport, well inside max_jumps.
    """
    runner = Runner(
        pages=[["p1"], ["p2"], ["p3"], ["p4"], ["p5"],
               ["q1"], ["q2"], ["q3"], ["q4"], ["q5"], ["alice"]],
        process_results=[False] * 10,
        private_flags=[True] * 10,
    )
    runner.interact_with_followers_direct("target", max_interactions=1)

    assert runner.escaped == 2, (
        f"{runner.escaped} transport(s) for two private zones — the jump counter is not "
        "advancing by one"
    )


def test_a_source_that_stays_private_is_given_up_on_not_flung_forever():
    """max_jumps is the ceiling, and reaching it requires the counter to advance by one.

    Five private zones offered, three transports allowed. Without the increment the run
    would keep flinging at a source that has already proven itself, burning the session
    budget in gestures instead of moving on.
    """
    zones = [[f"z{zone}{i}"] for zone in range(5) for i in range(5)]
    runner = Runner(
        pages=zones + [["alice"]],
        process_results=[False] * 25,
        private_flags=[True] * 25,
    )
    runner.interact_with_followers_direct("target", max_interactions=1)

    assert runner.escaped == 3, (
        f"{runner.escaped} transports for five private zones — expected exactly the three "
        "max_jumps allows, so the counter advances by one and the ceiling is reached"
    )


def test_the_transport_reports_the_gestures_it_actually_spent():
    """The seam between the loop and the transport: the loop bills its scroll budget with
    what comes back, so a transport that under-reports lets a run fling well past its cap.

    Tested directly rather than through the loop, because the budget is a local counter
    whose only visible effect is a stop hundreds of gestures later.
    """
    from taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.navigation_helpers import (
        DirectNavigationMixin,
    )

    class _Transporter(DirectNavigationMixin):
        def __init__(self):
            self.logger = _Logger()
            self.flung_with = None

        def _escape_private_zone(self, policy, jumps_done, source_followers=None):
            self.flung_with = (jumps_done, source_followers)
            return 7

        def _record_restriction_signal(self, **k):
            self.recorded = k

    from taktik.core.social_media.instagram.actions.business.workflows.common.private_streak_policy import (
        PrivateStreakPolicy,
    )

    transporter = _Transporter()
    moved = transporter._transport_out_of_private_zone(
        PrivateStreakPolicy(), private_streak=5, jumps_done=1,
        target_username="source", source_followers=900,
        account_username="me", encounter_order=42, tracker=_Tracker(),
    )

    assert moved == 7, "the loop would bill its scroll budget with the wrong number"
    assert transporter.flung_with == (1, 900), "the fling was not sized on the jump so far"
    # The recorded detection is dated by jump INDEX, which is the jump about to happen.
    assert transporter.recorded['jump_index'] == 2
    assert transporter.recorded['gestures'] == 7


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


def test_the_operator_stop_limits_reach_the_end_of_source_rule():
    """A limit the operator set must arrive where the run decides to stop.

    Found by mutation: resolving the limits from an empty config instead of the real one
    left every test green while silently ignoring what the operator asked for.
    """
    runner = Runner(pages=[["alice"], []])
    runner.interact_with_followers_direct(
        "target", max_interactions=1,
        config={'max_consecutive_known_usernames': 4},
    )

    # The two limits are the last two positional arguments of the end-of-source rule.
    assert runner.end_detection_args[-2:] == (4, None), (
        "the operator's stop limits did not reach _handle_scroll_and_end_detection"
    )


def test_without_a_username_limit_the_legacy_scroll_limit_still_applies():
    """The historical fallback: 20 fruitless scrolls, and only when nothing else is set."""
    runner = Runner(pages=[["alice"], []])
    runner.interact_with_followers_direct("target", max_interactions=1)

    assert runner.end_detection_args[-2:] == (None, 20)


def test_already_known_profiles_stay_out_of_the_rejection_buckets(monkeypatch):
    """'Already done' must never be tallied as 'rejected' — it inflates the run's stats."""
    monkeypatch.setattr(
        profile_processing.InstagramWorkflowStateService, "is_profile_skippable",
        staticmethod(lambda username, account_id, **k: (True, "already_processed")),
    )
    monkeypatch.setattr(
        profile_processing.InstagramWorkflowStateService, "get_skip_detail",
        staticmethod(lambda *a, **k: ""),
    )
    runner = Runner(pages=[["alice", "bob"], []])
    stats = runner.interact_with_followers_direct("target", max_interactions=5, account_id=7)

    assert stats['already_processed'] == 2
    assert stats['skipped'] == 0
    assert stats['filtered'] == 0
    assert runner.processed_calls == [], "opened a profile it already knew"


# --- what a run says when it stops -------------------------------------------
#
# Reproduced from institut.rentable, 2026-08-20..27. Eighteen runs filed COMPLETED /
# `completed`; exactly ONE had reached the budget the operator set. The other seventeen
# stopped on an exhausted source or an exhausted scroll allowance and said the same word.
# `completed` is the fallback of a loop that broke without setting a motive, so every silent
# exit reaches the operator as "the workflow did its job".


def _finalised_code(runner):
    """The stop reason a finalised run carried, by code."""
    assert runner.automation.helpers.finalized, "the run never finalised"
    _, reason = runner.automation.helpers.finalized[-1]
    return getattr(reason, 'code', str(reason))


def test_the_end_of_a_source_is_not_a_completed_run():
    """manon_nail_studio, 2026-08-25: stopped at 9 profiles of the 69 allowed, 14 min of
    the 125 allowed, having seen 24 of the target's 218 followers. Filed `completed`.

    The list ending is a perfectly good reason to stop. Calling it `completed` is what makes
    an operator believe their budget was spent.
    """
    runner = Runner(pages=[["alice"], [], []], real_empty_screen_handler=True)
    runner.detection_actions.suggestions_on_pages = {1, 2}

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert _finalised_code(runner) == 'end_of_list_suggestions', (
        "a run that ran out of followers reports the same motive as one that spent its budget"
    )


def test_an_empty_screen_is_not_the_end_of_the_list_on_its_own():
    """The root cause of the seventeen. `_handle_empty_followers_screen` concludes on ONE
    empty scan: suggestions section, no 'See more', a rescue scroll — then it breaks WITHOUT
    ever reading the screen that scroll produced.

    The main loop tolerates four consecutive empty scans before calling a list gone; this
    door has no tolerance at all. On a device, a scan that outruns the loading looks exactly
    like the end of a list.
    """
    runner = Runner(pages=[["alice"], [], ["bob", "carol"]], real_empty_screen_handler=True)
    runner.detection_actions.suggestions_on_pages = {1}

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert runner.processed_calls == ["alice", "bob", "carol"], (
        "followers were on screen after the rescue scroll and the run had already given up"
    )


def test_an_exhausted_scroll_allowance_says_so():
    """calystabeaute (88% of the list, 57 profiles of 69) and mbeautestudio48 (36%, 21 of 69),
    both stopped on exactly 100 scrolls — the hard-coded `max_scroll_attempts`.

    linstantbeautebaraqueville is the same stop reached differently: 63 scrolls plus 37
    private-zone transport flings, at 18% of a 517-follower list. The transport billing its
    gestures to the scroll budget is deliberate and tested (a transport that under-reports
    lets a run fling past its cap) — what is missing is the run SAYING the allowance ran out.
    """
    runner = Runner(pages=[["alice"]])

    runner.interact_with_followers_direct("target", max_interactions=50, finalize=True)

    assert runner.detection_actions.scrolls >= 100, "the scenario did not reach the cap"
    assert _finalised_code(runner) == 'scroll_budget', (
        "a run that ran out of scroll allowance mid-list reports itself as completed"
    )


# --- the list that had not finished loading ----------------------------------
#
# Operator report, 2026-08-27, watching the phones: the network in that room drops for
# seconds at a time, and the list is visibly still loading when the run calls it finished.
# The bot cannot tell the two apart — a list that has not loaded and a list that has ended
# are the same screen, zero clickable rows, and it decided on four scans spent in SIX
# seconds (measured on `sonailsbienetre`, 19:49:46 to 19:49:52, 35 profiles of 67 done).
#
# So: a safety net, and only that. It fires where the run was about to STOP, never while it
# is working, and a run that makes no progress does not get a second one.


def _sleepless(monkeypatch, on_sleep=None):
    """No real waiting in tests; `on_sleep` is what the passing time does to the screen."""
    slept = []
    def fake_sleep(seconds):
        slept.append(seconds)
        if on_sleep:
            on_sleep()
    monkeypatch.setattr(navigation_helpers.time, "sleep", fake_sleep)
    return slept


def test_a_list_still_loading_is_given_its_chance_before_the_run_ends(monkeypatch):
    """The reported case: the rows land during the wait, and the run carries on."""
    # Still empty after the immediate re-read (the outage outlasts a rescue scroll), so the
    # net is the only thing left between this run and a false end of list.
    runner = Runner(pages=[["alice"], [], [], ["bob", "carol"]], real_empty_screen_handler=True)
    runner.detection_actions.suggestions_on_pages = {1, 2}
    # The WAIT is what makes the list appear — not a scroll.
    slept = _sleepless(monkeypatch, on_sleep=lambda: setattr(runner.detection_actions, 'index', 3))

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert slept, "the run concluded without ever giving the list a chance"
    assert runner.processed_calls == ["alice", "bob", "carol"], (
        "the list came back during the wait and the run stopped anyway"
    )


def test_a_list_that_stays_empty_still_ends_the_run(monkeypatch):
    """The net must not turn a finished source into a run that waits for ever."""
    runner = Runner(pages=[["alice"], [], [], []], real_empty_screen_handler=True)
    runner.detection_actions.suggestions_on_pages = {1, 2, 3}
    slept = _sleepless(monkeypatch)

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert _finalised_code(runner) == 'end_of_list_suggestions'
    assert len(slept) <= 3, f"waited {len(slept)} times on a list that was simply finished"


def test_the_safety_net_never_fires_while_the_run_is_working(monkeypatch):
    """It is a net, not a toll: a healthy run must not pay a second for it."""
    runner = Runner(pages=[["alice", "bob", "carol"]])
    slept = _sleepless(monkeypatch)

    runner.interact_with_followers_direct("target", max_interactions=3, finalize=True)

    assert slept == [], "a run that spent its budget still waited on the network"


def test_a_run_that_made_no_progress_does_not_get_a_second_net(monkeypatch):
    """The anti-loop rule: a fresh chance is earned by interacting, not by waiting again.

    Without it, a list that comes back empty-handed — rows visible, none of them new —
    would buy another wait every lap and the run would never end.
    """
    runner = Runner(pages=[["alice"], [], [], ["alice"]], real_empty_screen_handler=True)
    runner.detection_actions.suggestions_on_pages = {1, 2}
    slept = _sleepless(monkeypatch, on_sleep=lambda: setattr(runner.detection_actions, 'index', 3))

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert len(slept) <= 3, (
        f"the run bought {len(slept)} waits without ever interacting again"
    )


def test_at_the_no_new_usernames_gate_a_familiar_row_proves_nothing(monkeypatch):
    """The gate where the screen was never empty needs a different question.

    "No new usernames" fires on a page FULL of rows we have already worked. Asking the net
    "are there rows?" there answers yes every time: it would report a recovery, burn the run's
    one chance on the page it was already stuck on, and change nothing. Only a row we have
    never seen proves the list actually moved.
    """
    runner = Runner(
        pages=[["alice"]],
        end_detection_results=[(False, None),
                               (True, main_loop.stop_reasons.end_of_list_repeated())],
    )
    slept = _sleepless(monkeypatch)

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert _finalised_code(runner) == 'end_of_list_repeated'
    assert len(slept) == 3, (
        f"the net stopped after {len(slept)} wait(s) — it took an already-known row for a return"
    )


def test_a_rate_limited_run_says_so_instead_of_blaming_navigation():
    """The five stops filed as `navigation_lost` that were Instagram saying "Try again later".

    Same symptom from inside the loop — the list is out of reach — and opposite decisions: a
    lost navigation is worth retrying, a block is worth stopping on, because acting again right
    after one is what turns a temporary limit into a lasting one.
    """
    class _Blocked:
        def is_action_blocked(self): return True

    runner = Runner(pages=[["alice"]], process_results=[None])
    runner.nav_actions = type('_N', (), {'problematic_page_detector': _Blocked()})()

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    status, reason = runner.automation.helpers.finalized[-1]
    assert getattr(reason, 'code', None) == 'action_blocked'
    assert status == "INTERRUPTED"
    assert [s['signal'] for s in runner.recorded_signals] == ['action_blocked'], (
        "the block was not written down, so nothing counts how often this account is limited"
    )


def test_a_genuinely_lost_navigation_is_still_a_lost_navigation():
    """The net must not relabel every failure as a block — that would hide real breakage."""
    class _NotBlocked:
        def is_action_blocked(self): return False

    runner = Runner(pages=[["alice"]], process_results=[None])
    runner.nav_actions = type('_N', (), {'problematic_page_detector': _NotBlocked()})()

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    _, reason = runner.automation.helpers.finalized[-1]
    assert getattr(reason, 'code', None) == 'navigation_lost'
    assert runner.recorded_signals == []


def test_a_lost_navigation_relaunches_the_app_and_carries_on():
    """The operator's ask: when the run loses its way, get it back on its feet.

    Bounded exactly like the network net — one relaunch per stretch of progress — and the
    scroll allowance is handed back, because a relaunch lands at the TOP of the list and the
    run has to scroll down past everything it already worked.
    """
    class _NotBlocked:
        def is_action_blocked(self): return False

    runner = Runner(pages=[["alice"]], process_results=[None], restartable=True)
    runner.nav_actions = type('_N', (), {'problematic_page_detector': _NotBlocked()})()

    runner.interact_with_followers_direct("target", max_interactions=2, finalize=True)

    assert runner.automation.device_manager.launches == [("com.instagram.android", True)]
    _, reason = runner.automation.helpers.finalized[-1]
    assert getattr(reason, 'code', None) != 'navigation_lost', (
        "the run relaunched successfully and still filed itself as lost"
    )


def test_a_blocked_account_is_never_relaunched():
    """The whole point of telling the two apart: relaunching after "Try again later" is acting
    again seconds after being told to stop."""
    class _Blocked:
        def is_action_blocked(self): return True

    runner = Runner(pages=[["alice"]], process_results=[None], restartable=True)
    runner.nav_actions = type('_N', (), {'problematic_page_detector': _Blocked()})()

    runner.interact_with_followers_direct("target", max_interactions=5, finalize=True)

    assert runner.automation.device_manager.launches == [], (
        "the app was relaunched while Instagram was rate-limiting the account"
    )
    assert _finalised_code(runner) == 'action_blocked'
