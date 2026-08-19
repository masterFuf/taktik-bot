"""The stop-reason catalogue must reproduce today's motives byte-for-byte.

The catalogue is introduced with no caller: on its own it changes nothing. What has to be proven
before any caller is routed through it is that its `text` is EXACTLY what each terminal path
emits today -- otherwise the migration would silently reword what a run reports, and the desktop
app (which still matches those sentences with regular expressions) would stop recognising them.

Two levels of proof, deliberately:

- the SessionManager motives are compared against the REAL SessionManager, driven to each of its
  stop conditions. Nothing is transcribed by hand, so the test cannot agree with a typo;
- the other motives, whose emitters need a device to run, are compared against literals copied
  from their source. Weaker, but it is the same comparison the migration will make.
"""

from datetime import datetime, timedelta

from taktik.core.social_media.instagram.workflows.management.session import stop_reasons as sr
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


# -- Level 1: proven against the real SessionManager ---------------------------

def _manager(**settings) -> SessionManager:
    return SessionManager({'session_settings': settings})


def test_duration_matches_the_real_session_manager():
    sm = _manager(session_duration_minutes=45)
    sm.session_start_time = datetime.now() - timedelta(minutes=46)

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.duration_cap(45).text


def test_profiles_cap_matches_the_real_session_manager():
    sm = _manager(total_profiles_limit=30)
    sm.counters['profiles_processed'] = 30

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.profiles_cap(30, 30).text


def test_follows_cap_matches_the_real_session_manager():
    # The motive from the audit: a cap nobody set, derived from profiles x follow%.
    sm = _manager(total_follows_limit=5)
    sm.counters['follows'] = 5

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.follows_cap(5, 5).text


def test_likes_cap_matches_the_real_session_manager():
    sm = _manager(total_likes_limit=63)
    sm.counters['likes'] = 63

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.likes_cap(63, 63).text


def test_daily_budget_matches_the_real_session_manager():
    sm = _manager(warmup_policy={'max_actions_per_day': 250})
    sm.set_daily_usage_provider(lambda: {'total': 250})

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.daily_budget(250, 250).text


def test_session_action_cap_matches_the_real_session_manager():
    sm = _manager(warmup_policy={'max_actions_per_session': 100})
    sm.counters['likes'] = 60
    sm.counters['follows'] = 25
    sm.counters['comments'] = 15

    keep_going, emitted = sm.should_continue()

    assert keep_going is False
    assert emitted == sr.session_action_cap(100, 100).text


# -- Level 2: compared against the literals of the device-bound emitters --------

def test_navigation_motives_keep_their_exact_wording():
    # navigation_helpers.py -- thousands separators included, they reach the app's regex.
    assert sr.end_of_list(1234, 5678).text == "End of followers list (1,234/5,678 seen)"
    assert sr.end_of_list_repeated().text == "End of followers list (same profiles repeated)"
    assert sr.end_of_list_suggestions().text == "End of followers list (suggestions section)"
    assert sr.no_new_profiles(472).text == "No new followers found (472 profiles seen)"
    assert sr.known_streak(150, 472).text == (
        "No new followers after 150 known usernames in a row (472 seen)"
    )
    assert sr.scroll_streak(10, 472).text == (
        "No new followers after 10 scroll attempts (472 seen)"
    )


def test_generic_motives_keep_their_exact_wording():
    assert sr.completed(30).text == "Workflow completed (30 interactions)"
    assert sr.sources_exhausted().text == "Sources exhausted (no further progress)"
    assert sr.manual_stop().text == "Manual stop (Ctrl+C)"


def test_bare_code_motives_still_emit_their_bare_code():
    # These paths already emitted a snake_case code. The catalogue renames some of them, but the
    # TEXT must not move until no consumer reads it any more.
    assert sr.no_valid_post().text == "no_valid_post"
    assert sr.no_new_post().text == "no_new_post"
    assert sr.empty_plan().text == "empty_plan"
    assert sr.no_targets().text == "no_targets"
    assert sr.navigation_lost().text == "navigation_lost"
    assert sr.posts_cap(12, 12).text == "budget_reached"
    assert sr.posts_examined_cap(60, 60).text == "max_posts_examined"
    assert sr.list_unavailable().text == "followers_list_unavailable"


# -- Catalogue integrity -------------------------------------------------------

def _every_reason():
    """One instance of every motive, so the catalogue can be inspected as a whole."""
    return [
        sr.duration_cap(60), sr.profiles_cap(1, 2), sr.follows_cap(1, 2), sr.likes_cap(1, 2),
        sr.daily_budget(1, 2), sr.session_action_cap(1, 2), sr.posts_cap(1, 2),
        sr.end_of_list(1, 2), sr.end_of_list_repeated(), sr.end_of_list_suggestions(),
        sr.no_new_profiles(1), sr.known_streak(1, 2), sr.scroll_streak(1, 2),
        sr.sources_exhausted(), sr.no_valid_post(), sr.no_new_post(), sr.posts_examined_cap(1, 2),
        sr.completed(1),
        sr.navigation_lost(), sr.list_unavailable(), sr.empty_plan(), sr.no_targets(),
        sr.manual_stop(),
    ]


def test_codes_are_unique():
    codes = [reason.code for reason in _every_reason()]
    assert len(codes) == len(set(codes)), "two motives share a code"


def test_no_motive_is_empty_or_untyped():
    families = {sr.FAMILY_CAP, sr.FAMILY_EXHAUSTED, sr.FAMILY_COMPLETED,
                sr.FAMILY_DEGRADED, sr.FAMILY_EXTERNAL}
    for reason in _every_reason():
        assert reason.code, "a motive has no code"
        assert reason.text, f"{reason.code} has no text"
        assert reason.family in families, f"{reason.code} has an unknown family"


def test_event_fields_stay_additive():
    # `reason` must keep carrying the legacy sentence: a desktop build predating the catalogue
    # reads that field and nothing else.
    fields = sr.follows_cap(5, 5).event_fields()

    assert fields == {
        "reason": "Follows limit reached (5/5)",
        "reason_code": "follows_cap",
        "reason_params": {"count": 5, "limit": 5},
    }


def test_params_cannot_be_mutated_through_the_event():
    reason = sr.follows_cap(5, 5)
    reason.event_fields()["reason_params"]["count"] = 999

    assert reason.params["count"] == 5
