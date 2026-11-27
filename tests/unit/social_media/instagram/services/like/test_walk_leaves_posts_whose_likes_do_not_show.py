"""The walk of a profile's posts leaves them when their likes do not show, and the run goes on.

Measured on 2026-11-27 over 14 runs: on a Pixel 3a, 29 of 58 double taps on a video were read as not
given, none on a photo. Three in a row stopped the run (`like_unconfirmed`), nine runs in two days,
on phones that liked well everywhere else. The walk now goes to the next profile on three in a row;
the run stops when the profiles after it show none either (`like_confirmation`).

The walk is the production one, its screen readers stubbed; a like not seen is what
`_like_outcome` files (`test_like_plays_one_gesture.py` holds that on real dumps).
"""

import taktik.core.shared.behavior.like_method as like_method
import taktik.core.social_media.instagram.services.like.orchestration as module
import taktik.core.social_media.instagram.services.like.post_navigation as post_navigation
from loguru import logger
from taktik.core.shared.diagnostics import like_confirmation, run_halt
from taktik.core.social_media.instagram.services.like.orchestration import LikeOrchestration

TO_LEAVE = like_confirmation.UNCONFIRMED_LIKES_BEFORE_LEAVING


def _walk(monkeypatch, like_shows):
    """A profile's posts walked with `like_shows(post_number)` saying whether each like shows
    (None: no gesture was played, its heart could not be shown). Returns (stats, posts the walk
    advanced to)."""
    host = object.__new__(LikeOrchestration)
    host.default_config = {}
    host.logger = logger
    host._open_entry_post_of_profile = lambda *_args, **_kwargs: True
    host._behavior_reading_scale = lambda *_args, **_kwargs: 1.0
    host._is_current_post_reel = lambda: False
    host._glance_at_post = lambda: None
    played = []
    # One signature per post: the walk counts the posts it has not seen yet.
    host._current_post_signature = lambda: f"post {len(played)}"
    host._extract_likes_count_from_ui = lambda **_kwargs: 12 + len(played)
    host._extract_comments_count_from_ui = lambda **_kwargs: 3
    host._is_post_already_liked = lambda: False
    host._action_timestamp = lambda: "now"
    host._notify_gesture = lambda *_args, **_kwargs: None
    host._human_like_delay = lambda *_args, **_kwargs: None
    host._return_to_profile_from_post = lambda: None
    advances = []
    host._advance_or_exit_reel = lambda *_args, **_kwargs: advances.append(True) or True

    def engagement(*_args, **_kwargs):
        played.append(True)
        shows = like_shows(len(played))
        if shows is None:
            return False, False
        if shows:
            like_confirmation.like_seen()
            return True, False
        like_confirmation.like_not_seen()
        return False, False

    host._run_engagement_sequence = engagement
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(like_method.random, "random", lambda: 0.0)
    monkeypatch.setattr(post_navigation, "content_dwell", lambda _prose: 0.0)
    monkeypatch.setattr(module, "plan_engagement_sequence", lambda *_args: ("like",))
    monkeypatch.setattr(module, "check_post_terms", lambda *_args, **_kwargs: type("Verdict", (), {"allowed": True})())
    stats = host.like_posts_with_sequential_scroll("target", max_likes=5, profile_data={"posts_count": 30})
    return stats, len(advances)


def test_the_posts_are_left_on_the_likes_not_seen_in_a_row_and_the_run_goes_on(monkeypatch):
    stats, advanced = _walk(monkeypatch, like_shows=lambda _post: False)

    assert stats["likes_refused"] == TO_LEAVE
    assert advanced == TO_LEAVE - 1, "the walk went to a next post after the last like not seen"
    assert run_halt.arret_demande() is None


def test_a_like_that_shows_keeps_the_walk_on_the_posts(monkeypatch):
    # Two not seen, one seen, two not seen: never three in a row.
    stats, _advanced = _walk(monkeypatch, like_shows=lambda post: post == TO_LEAVE)

    assert stats["posts_liked"] == 1
    assert stats["likes_refused"] > TO_LEAVE - 1, "the walk left the posts although a like showed"


def test_the_next_profile_is_walked_although_the_one_before_was_left(monkeypatch):
    _walk(monkeypatch, like_shows=lambda _post: False)

    stats, _advanced = _walk(monkeypatch, like_shows=lambda _post: True)

    assert stats["posts_liked"] == 5


def test_the_next_profile_is_not_left_for_a_like_that_played_no_gesture(monkeypatch):
    _walk(monkeypatch, like_shows=lambda _post: False)

    stats, _advanced = _walk(monkeypatch, like_shows=lambda post: None if post == 1 else True)

    assert stats["posts_liked"] == 5, "what was asked of the posts before was held against these"


def test_profiles_left_one_after_the_other_stop_the_run(monkeypatch):
    for _ in range(like_confirmation.UNCONFIRMED_LIKES_BEFORE_HALT // TO_LEAVE):
        assert run_halt.arret_demande() is None
        _walk(monkeypatch, like_shows=lambda _post: False)

    assert run_halt.arret_demande()["code"] == run_halt.LIKE_UNCONFIRMED
