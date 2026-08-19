"""A spent budget must remove its action from the plan, and leave the rest of the run alone.

This is the chain the change rests on: SessionManager says which budgets are spent, and the
plan builder drops exactly those intents. Both halves were tested separately; what was missing
is the proof that they agree on the vocabulary, since a typo in an intent name silently masks
nothing at all and the run keeps following past its ceiling.

The behaviour being locked in: a run allowed 5 follows over 30 profiles used to STOP at the
fifth follow -- around profile 26 on the default settings, taking the likes and the stories
with it. It now stops following and keeps going.
"""

from datetime import datetime, timedelta

from taktik.core.shared.behavior.interaction_plan import InteractionPlan, mask_exhausted_intents
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


def _manager(**settings) -> SessionManager:
    return SessionManager({'session_settings': settings})


def _full_plan() -> InteractionPlan:
    """A profile the operator wants everything done to."""
    return InteractionPlan(
        like_target=3,
        do_follow=True,
        do_comment=True,
        max_comments=1,
        do_watch_story=True,
        story_like_slot=0,
        max_story_slides=3,
        do_story_like=True,
        max_story_likes=1,
    )


def test_a_spent_follow_budget_drops_the_follow_and_nothing_else():
    session = _manager(total_follows_limit=5, total_likes_limit=63)
    session.counters['follows'] = 5

    plan, masked = mask_exhausted_intents(_full_plan(), session.exhausted_intents())

    assert masked == ['follow']
    assert plan.do_follow is False
    # Everything the operator asked for besides the follow survives -- that is the whole point.
    assert plan.like_target == 3
    assert plan.do_comment is True
    assert plan.do_watch_story is True
    assert plan.do_story_like is True


def test_a_spent_like_budget_drops_the_likes_and_nothing_else():
    session = _manager(total_follows_limit=5, total_likes_limit=63)
    session.counters['likes'] = 63

    plan, masked = mask_exhausted_intents(_full_plan(), session.exhausted_intents())

    assert masked == ['like']
    assert plan.like_target == 0
    assert plan.do_follow is True
    assert plan.do_watch_story is True


def test_both_budgets_spent_still_leaves_stories_and_comments():
    session = _manager(total_follows_limit=5, total_likes_limit=63)
    session.counters['follows'] = 5
    session.counters['likes'] = 63

    keep_going, _ = session.should_continue()
    plan, masked = mask_exhausted_intents(_full_plan(), session.exhausted_intents())

    assert keep_going is True, "spent per-type budgets must not end the run"
    assert sorted(masked) == ['follow', 'like']
    assert plan.do_follow is False and plan.like_target == 0
    assert plan.do_comment is True and plan.do_watch_story is True


def test_an_untouched_budget_returns_the_plan_as_it_was():
    session = _manager(total_follows_limit=5, total_likes_limit=63)
    session.counters['follows'] = 4

    plan, masked = mask_exhausted_intents(_full_plan(), session.exhausted_intents())

    assert masked == []
    assert plan == _full_plan()


def test_the_session_still_ends_on_a_global_budget():
    # Only the per-TYPE ceilings became non-terminal. The whole-run guards must still stop it,
    # otherwise removing the per-type stops would have left the session unbounded.
    duration = _manager(session_duration_minutes=45)
    duration.session_start_time = datetime.now() - timedelta(minutes=46)
    assert duration.should_continue()[0] is False

    profiles = _manager(total_profiles_limit=30)
    profiles.counters['profiles_processed'] = 30
    assert profiles.should_continue()[0] is False

    action_cap = _manager(warmup_policy={'max_actions_per_session': 10})
    action_cap.counters['likes'] = 10
    assert action_cap.should_continue()[0] is False
