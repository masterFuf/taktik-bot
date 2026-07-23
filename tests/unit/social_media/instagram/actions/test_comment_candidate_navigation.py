from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class _CommentOnlyHarness:
    like_posts_with_sequential_scroll = (
        LikeOrchestration.like_posts_with_sequential_scroll
    )
    default_config = {}
    _notify_gesture = staticmethod(LikeOrchestration._notify_gesture)

    def __init__(self, comment_results):
        self.logger = _Logger()
        self._comment_results = iter(comment_results)
        self._signature = 0
        self.returned = False
        self.sequences = []

    def _open_entry_post_of_profile(self, *_args, **_kwargs):
        return True

    def _behavior_reading_scale(self, _context):
        return 0

    def _is_current_post_reel(self):
        return False

    def _extract_likes_count_from_ui(self, **_kwargs):
        self._signature += 1
        return self._signature

    def _extract_comments_count_from_ui(self, **_kwargs):
        return 0

    def _run_engagement_sequence(
        self,
        sequence,
        _username,
        _custom_comments,
        _comment_template_category,
        _config,
    ):
        self.sequences.append(sequence)
        return False, next(self._comment_results)

    def _advance_or_exit_reel(self, *_args):
        return True

    def _human_like_delay(self, _kind):
        return None

    def _return_to_profile_from_post(self):
        self.returned = True


def test_comment_candidate_runs_when_like_target_is_zero(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.orchestration.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.actions.like.orchestration.plan_engagement_sequence",
        lambda do_like, do_comment: ["comment"] if do_comment and not do_like else [],
    )
    harness = _CommentOnlyHarness([False, True])

    result = harness.like_posts_with_sequential_scroll(
        "filmmaker",
        max_likes=0,
        profile_data={"posts_count": 4},
        should_like=False,
        should_comment=True,
        max_comments=1,
    )

    assert result["posts_seen"] == 2
    assert result["posts_liked"] == 0
    assert result["posts_commented"] == 1
    assert result["success"] is True
    assert harness.sequences == [["comment"], ["comment"]]
    assert harness.returned is True
