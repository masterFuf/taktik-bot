"""The plan decides how many posts are liked; the walk through the posts decides which.

The profile's plan has already drawn its likes (« Plan final @x: likes=1 »). The walk used to draw
each post again (0.70 x a position factor) and could like none of them: on a profile of one post,
44 % of the visits gave no like, and the log blamed a like that « did not land ». The draw keeps its
role of a natural choice among the posts, but once the likes still owed equal the posts left to
see, each of them is liked: the walk reaches the plan's number whenever the profile has enough posts.
"""

import taktik.core.social_media.instagram.services.like.orchestration as module
import taktik.core.shared.behavior.like_method as like_method
import taktik.core.social_media.instagram.services.like.post_navigation as post_navigation
from taktik.core.social_media.instagram.services.like.orchestration import LikeOrchestration

MISSES = 0.99  # a draw that never likes
HITS = 0.0     # a draw that always likes


class _Log:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


def _walk(monkeypatch, *, posts_count, draw, like_takes=True, already_liked=False):
    host = object.__new__(LikeOrchestration)
    host.default_config = {}
    host.logger = _Log()
    host._open_entry_post_of_profile = lambda *_args, **_kwargs: True
    host._is_current_post_reel = lambda: False
    seen = {"n": 0}

    def _likes_count(**_kwargs):
        return 100 + seen["n"]  # each post its own counters, so each one is new

    host._extract_likes_count_from_ui = _likes_count
    host._extract_comments_count_from_ui = lambda **_kwargs: 3
    host._visit_signature = lambda likes, comments, is_reel: f"post-{likes}"
    host._glance_at_post = lambda: None
    host._is_post_already_liked = lambda: already_liked
    liked_on = []

    def _sequence(*_args, **_kwargs):
        liked_on.append(seen["n"])
        return (like_takes, False)

    host._run_engagement_sequence = _sequence
    host._action_timestamp = lambda: "t"
    host._notify_gesture = lambda *_args, **_kwargs: None
    host._human_like_delay = lambda *_args, **_kwargs: None
    host._return_to_profile_from_post = lambda: None

    def _advance(*_args, **_kwargs):
        seen["n"] += 1
        return True

    host._advance_or_exit_reel = _advance
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(like_method.random, "random", lambda: draw)
    monkeypatch.setattr(post_navigation, "content_dwell", lambda _prose: 0.0)
    monkeypatch.setattr(module, "plan_engagement_sequence", lambda *_args: ("like",))
    return host, liked_on


def test_a_one_post_profile_gets_the_like_its_plan_decided(monkeypatch):
    host, liked_on = _walk(monkeypatch, posts_count=1, draw=MISSES)

    result = host.like_posts_with_sequential_scroll("user_1", max_likes=1, profile_data={"posts_count": 1})

    assert result["posts_liked"] == 1
    assert liked_on == [0]


def test_the_plan_s_number_is_reached_when_the_draw_passes_the_first_posts(monkeypatch):
    host, liked_on = _walk(monkeypatch, posts_count=3, draw=MISSES)

    result = host.like_posts_with_sequential_scroll("user_1", max_likes=2, profile_data={"posts_count": 3})

    assert result["posts_liked"] == 2
    assert liked_on == [1, 2], "the draw passed the first post, the two left were owed"
    assert result["passed_by_draw"] == 1


def test_the_draw_still_chooses_which_posts_when_there_is_room(monkeypatch):
    host, liked_on = _walk(monkeypatch, posts_count=10, draw=HITS)

    result = host.like_posts_with_sequential_scroll("user_1", max_likes=2, profile_data={"posts_count": 10})

    assert result["posts_liked"] == 2
    assert liked_on == [0, 1]
    assert result["passed_by_draw"] == 0


def test_a_like_the_screen_refuses_is_counted_as_refused(monkeypatch):
    host, _ = _walk(monkeypatch, posts_count=1, draw=MISSES, like_takes=False)

    result = host.like_posts_with_sequential_scroll("user_1", max_likes=1, profile_data={"posts_count": 1})

    assert result["posts_liked"] == 0
    assert result["likes_refused"] == 1


def test_an_already_liked_post_is_counted_as_such(monkeypatch):
    host, liked_on = _walk(monkeypatch, posts_count=1, draw=MISSES, already_liked=True)

    result = host.like_posts_with_sequential_scroll("user_1", max_likes=1, profile_data={"posts_count": 1})

    assert result["posts_liked"] == 0
    assert liked_on == []
    assert result["already_liked"] == 1
