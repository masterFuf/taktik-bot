import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as module
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)


class _Log:
    def debug(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def success(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


def test_last_requested_like_stops_before_opening_another_post(monkeypatch):
    host = object.__new__(LikeOrchestration)
    host.default_config = {}
    host.logger = _Log()
    host._open_entry_post_of_profile = lambda *_args, **_kwargs: True
    host._behavior_reading_scale = lambda *_args, **_kwargs: 1.0
    host._is_current_post_reel = lambda: False
    host._extract_likes_count_from_ui = lambda **_kwargs: 12
    host._extract_comments_count_from_ui = lambda **_kwargs: 3
    host._is_post_already_liked = lambda: False
    host._run_engagement_sequence = lambda *_args, **_kwargs: (True, False)
    host._action_timestamp = lambda: "now"
    host._notify_gesture = lambda *_args, **_kwargs: None
    host._human_like_delay = lambda *_args, **_kwargs: None
    host._return_to_profile_from_post = lambda: None
    advances = []
    host._advance_or_exit_reel = lambda *_args, **_kwargs: advances.append(True) or True

    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module.random, "random", lambda: 0.0)
    monkeypatch.setattr(module, "content_dwell", lambda _prose: 0.0)
    monkeypatch.setattr(module, "plan_engagement_sequence", lambda *_args: ("like",))

    result = host.like_posts_with_sequential_scroll(
        "target",
        max_likes=1,
        profile_data={"posts_count": 10},
    )

    assert result["posts_liked"] == 1
    assert result["posts_seen"] == 1
    assert advances == []
