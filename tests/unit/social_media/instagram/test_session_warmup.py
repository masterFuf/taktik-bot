"""Warmup guardrail enforced by SessionManager: cadence floor + daily-budget stop.

The desktop app injects numbers (session_settings.warmup_policy) computed from the account's age;
the bot applies them. Absent (standalone) -> no enforcement, behaviour unchanged.
"""

from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


def _sm(warmup=None, delay=None):
    settings = {}
    if warmup is not None:
        settings['warmup_policy'] = warmup
    if delay is not None:
        settings['delay_between_actions'] = delay
    return SessionManager({'session_settings': settings})


# ── Cadence floor ──────────────────────────────────────────────────────────────

def test_floor_raises_the_default_natural_delay():
    # Default 'natural' alone yields 0-1s (see test_session_pacing); the floor must lift it.
    sm = _sm(warmup={'min_action_gap_seconds': 5})
    for _ in range(50):
        assert sm.get_delay_between_actions() >= 5


def test_floor_never_lowers_a_higher_delay():
    # An explicit 10-12s delay is already above the 5s floor -> untouched.
    sm = _sm(warmup={'min_action_gap_seconds': 5}, delay={'min': 10, 'max': 12})
    for _ in range(50):
        assert 10 <= sm.get_delay_between_actions() <= 12


def test_no_floor_leaves_delay_unchanged():
    sm = _sm(warmup={'min_action_gap_seconds': 0})
    for _ in range(50):
        assert 0 <= sm.get_delay_between_actions() <= 1


# ── Daily budget stop ──────────────────────────────────────────────────────────

def test_no_provider_means_cap_is_a_noop():
    # Caps present but no usage provider (e.g. account not resolved) -> never stops on budget.
    sm = _sm(warmup={'max_actions_per_day': 10})
    ok, _ = sm.should_continue()
    assert ok is True


def test_no_caps_means_cap_is_a_noop():
    sm = _sm(warmup={})
    sm.set_daily_usage_provider(lambda: {'total': 9999})
    ok, _ = sm.should_continue()
    assert ok is True


def test_stops_when_daily_action_budget_reached():
    sm = _sm(warmup={'max_actions_per_day': 50})
    sm.set_daily_usage_provider(lambda: {'total': 50, 'follows': 0, 'comments': 0})
    ok, reason = sm.should_continue()
    assert ok is False
    assert 'action budget' in reason


def test_continues_when_under_daily_budget():
    sm = _sm(warmup={'max_actions_per_day': 50})
    sm.set_daily_usage_provider(lambda: {'total': 49, 'follows': 0, 'comments': 0})
    ok, _ = sm.should_continue()
    assert ok is True


def test_follow_subcap_does_not_stop_the_session():
    # A spent sub-quota disables ITS action, it does not end the run: the session still has
    # 480 actions of global budget to like and watch stories with.
    sm = _sm(warmup={'max_actions_per_day': 500, 'max_follows_per_day': 10})
    sm.set_daily_usage_provider(lambda: {'total': 20, 'follows': 10, 'comments': 0})
    ok, _ = sm.should_continue()
    assert ok is True
    assert sm.exhausted_intents() == {'follow'}


def test_comment_subcap_does_not_stop_the_session():
    sm = _sm(warmup={'max_actions_per_day': 500, 'max_comments_per_day': 5})
    sm.set_daily_usage_provider(lambda: {'total': 20, 'follows': 0, 'comments': 5})
    ok, _ = sm.should_continue()
    assert ok is True
    assert sm.exhausted_intents() == {'comment'}


def test_both_subcaps_can_be_exhausted_at_once():
    sm = _sm(warmup={'max_actions_per_day': 500, 'max_follows_per_day': 10, 'max_comments_per_day': 5})
    sm.set_daily_usage_provider(lambda: {'total': 20, 'follows': 12, 'comments': 7})
    assert sm.should_continue()[0] is True
    assert sm.exhausted_intents() == {'follow', 'comment'}


def test_no_quota_is_exhausted_under_the_caps():
    sm = _sm(warmup={'max_actions_per_day': 500, 'max_follows_per_day': 10, 'max_comments_per_day': 5})
    sm.set_daily_usage_provider(lambda: {'total': 20, 'follows': 9, 'comments': 4})
    assert sm.exhausted_intents() == set()


def test_exhausted_quotas_fail_open_without_provider_or_on_error():
    # Standalone (no provider) and a failing read must both mask nothing.
    sm = _sm(warmup={'max_follows_per_day': 1})
    assert sm.exhausted_intents() == set()

    def boom():
        raise RuntimeError('db down')

    sm.set_daily_usage_provider(boom)
    assert sm.exhausted_intents() == set()


def test_provider_error_does_not_kill_the_session():
    # A failing read must never stop the run — the front gate is the primary guard.
    def boom():
        raise RuntimeError('db down')

    sm = _sm(warmup={'max_actions_per_day': 1})
    sm.set_daily_usage_provider(boom)
    ok, _ = sm.should_continue()
    assert ok is True


def test_update_config_refreshes_warmup_caps():
    sm = _sm(warmup={'max_actions_per_day': 500})
    sm.set_daily_usage_provider(lambda: {'total': 60, 'follows': 0, 'comments': 0})
    assert sm.should_continue()[0] is True
    # A config swap lowering the cap below today's total must now stop.
    sm.update_config({'session_settings': {'warmup_policy': {'max_actions_per_day': 50}}})
    assert sm.should_continue()[0] is False


# ── Per-session action cap ───────────────────────────────────────────────────────

def test_stops_when_session_action_cap_reached():
    # Written actions this session (like/follow/comment) hitting the cap ends the session,
    # independent of the daily budget (no provider needed).
    sm = _sm(warmup={'max_actions_per_session': 25})
    sm.counters['likes'] = 15
    sm.counters['follows'] = 7
    sm.counters['comments'] = 3  # 25 total
    ok, reason = sm.should_continue()
    assert ok is False
    assert 'Session action cap' in reason


def test_continues_when_under_session_cap():
    sm = _sm(warmup={'max_actions_per_session': 25})
    sm.counters['likes'] = 20
    sm.counters['follows'] = 3  # 23 total
    ok, _ = sm.should_continue()
    assert ok is True


def test_session_cap_ignores_story_views():
    # Story VIEWS are passive and excluded from the budget; they must not count toward the cap.
    sm = _sm(warmup={'max_actions_per_session': 25})
    sm.counters['likes'] = 5
    sm.counters['stories_watched'] = 100
    ok, _ = sm.should_continue()
    assert ok is True


def test_no_session_cap_is_a_noop():
    sm = _sm(warmup={'max_actions_per_session': 0})
    sm.counters['likes'] = 999
    ok, _ = sm.should_continue()
    assert ok is True


def test_decision_budget_snapshot_exposes_live_usage_and_hard_caps():
    sm = _sm(warmup={
        'max_actions_per_day': 50,
        'max_follows_per_day': 10,
        'max_comments_per_day': 5,
        'max_actions_per_session': 25,
    })
    sm.set_daily_usage_provider(
        lambda: {'total': 23, 'follows': 4, 'comments': 2}
    )
    sm.counters['likes'] = 3
    sm.counters['follows'] = 1
    sm.counters['comments'] = 1

    snapshot = sm.decision_budget_snapshot()

    assert snapshot['daily'] == {'total': 23, 'follows': 4, 'comments': 2}
    assert snapshot['session'] == {
        'total': 5, 'likes': 3, 'follows': 1, 'comments': 1,
    }
    assert snapshot['caps'] == {
        'max_actions_per_day': 50,
        'max_follows_per_day': 10,
        'max_comments_per_day': 5,
        'max_actions_per_session': 25,
    }
