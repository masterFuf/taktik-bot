"""The safety net's last resort: leave the list and open it again.

Why it exists. Waiting was the only remedy the net could try, and it was a test whose answer
was written in advance: on the gate where the page is full but exhausted it filters out every
row it has already seen and never scrolls, so nothing new can appear. Measured over the runs
kept on disk, 52 give-ups against a single recovery.

Reopening asks the other question — is the VIEW dead, or is Instagram refusing to serve this
list at all — and the two call for opposite moves. It only runs where the screen is EMPTY: on a
full page there is a position worth keeping, and leaving would trade it for rows already worked.
"""

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.navigation_helpers as navigation_helpers
from taktik.core.social_media.instagram.actions.business.workflows.common.list_reload_policy import (
    ListReloadPolicy,
)
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


class _Logger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _Detection:
    """Serves one screen per call, so a test can script "empty, empty, empty, then full"."""

    def __init__(self, screens):
        self.screens = list(screens)
        self.calls = 0

    def get_visible_followers_with_elements(self):
        self.calls += 1
        return self.screens.pop(0) if self.screens else []


class _NavActions:
    def __init__(self, reached_profile=True, opened=True):
        self.reached_profile = reached_profile
        self.opened = opened
        self.opened_lists = []

    def navigate_to_profile(self, username, **kwargs):
        return self.reached_profile

    def open_followers_list(self):
        self.opened_lists.append('followers')
        return self.opened

    def open_following_list(self):
        self.opened_lists.append('following')
        return self.opened


class _Workflow(navigation_helpers.DirectNavigationMixin):
    def __init__(self, screens, nav_actions=None):
        self.logger = _Logger()
        self.detection_actions = _Detection(screens)
        self.nav_actions = nav_actions or _NavActions()

    def _human_like_delay(self, kind):
        pass


ROW = [{'username': 'someone'}]


@pytest.fixture
def emitted(monkeypatch):
    """Capture the telemetry: it is the measurement, not decoration."""
    events = []
    monkeypatch.setattr(navigation_helpers, 'emit_step',
                        lambda category, **kw: events.append((category, kw)))
    monkeypatch.setattr(navigation_helpers.time, 'sleep', lambda _s: None)
    return events


def _actions(events):
    return [kw.get('action') for _category, kw in events]


def _detail(events, action):
    return next(kw for _c, kw in events if kw.get('action') == action)


def test_the_reopen_brings_the_rows_back(emitted):
    """An empty view that fills up once reopened: the source was never finished."""
    workflow = _Workflow(screens=[[], [], [], ROW])  # 3 waits empty, then the reopened screen

    came_back = workflow._list_came_back_after_waiting(
        ListReloadPolicy(), stop_reasons.list_unavailable(), total_usernames_seen=36,
        already_seen=None, reopen=lambda: True)

    assert came_back is True
    assert 'recovered_after_reopen' in _actions(emitted)
    assert 'gave_up' not in _actions(emitted)


def test_still_empty_after_reopening_is_the_real_answer(emitted):
    """Instagram is not serving this list — and the metric must say the reopen was tried."""
    workflow = _Workflow(screens=[[], [], [], []])

    came_back = workflow._list_came_back_after_waiting(
        ListReloadPolicy(), stop_reasons.list_unavailable(), total_usernames_seen=36,
        already_seen=None, reopen=lambda: True)

    assert came_back is False
    assert _detail(emitted, 'gave_up')['reopened'] == 'ok'


def test_a_reopen_that_cannot_reach_the_screen_is_not_the_same_answer(emitted):
    """Failing to get back to the list says nothing about Instagram. Keep the two apart."""
    workflow = _Workflow(screens=[[], [], []])

    came_back = workflow._list_came_back_after_waiting(
        ListReloadPolicy(), stop_reasons.list_unavailable(), total_usernames_seen=36,
        already_seen=None, reopen=lambda: False)

    assert came_back is False
    assert _detail(emitted, 'gave_up')['reopened'] == 'failed'


def test_a_full_but_exhausted_page_gives_up_without_leaving(emitted):
    """The gate that passes `already_seen` holds a POSITION, so its caller passes no reopen.

    What the net owes here is an honest metric: `not_tried` must not read like a screen that
    stayed empty after we went and looked again.
    """
    workflow = _Workflow(screens=[ROW, ROW, ROW])

    came_back = workflow._list_came_back_after_waiting(
        ListReloadPolicy(), stop_reasons.end_of_list_repeated(), total_usernames_seen=55,
        already_seen={'someone'}, reopen=None)

    assert came_back is False
    assert _detail(emitted, 'gave_up')['reopened'] == 'not_tried'


def test_a_list_that_was_only_slow_never_pays_for_a_reopen(emitted):
    """The reopen is a LAST resort: a wait that works must end the net there and then."""
    reopened = []
    workflow = _Workflow(screens=[[], ROW])

    came_back = workflow._list_came_back_after_waiting(
        ListReloadPolicy(), stop_reasons.list_unavailable(), total_usernames_seen=8,
        already_seen=None, reopen=lambda: reopened.append(True) or True)

    assert came_back is True
    assert reopened == [], "the list came back on its own — no reason to leave it"
    assert _actions(emitted) == ['recovered']


def test_reopening_follows_the_interaction_type():
    """A `following` run must not come back on the followers tab — that is a different list."""
    nav = _NavActions()
    workflow = _Workflow(screens=[], nav_actions=nav)

    assert workflow._reopen_source_list('target', {'interaction_type': 'following'}, 0, False)
    assert nav.opened_lists == ['following']

    assert workflow._reopen_source_list('target', {}, 0, False)
    assert nav.opened_lists == ['following', 'followers']


def test_a_reopen_that_never_reaches_the_profile_reports_failure():
    workflow = _Workflow(screens=[], nav_actions=_NavActions(reached_profile=False))
    assert workflow._reopen_source_list('target', {}, 0, False) is False


def test_a_reopen_whose_list_will_not_open_reports_failure():
    workflow = _Workflow(screens=[], nav_actions=_NavActions(opened=False))
    assert workflow._reopen_source_list('target', {}, 0, False) is False
