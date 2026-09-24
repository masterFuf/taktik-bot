"""The post-analysis hook must pass `record_as` through to the like it wraps.

`like_current_post(record_as=...)` is how the hashtag posts pass files a like at the gesture
(2026-09-24). With `postAnalysis` on and `smartComments` off, the AI hooks replace that method
by a wrapper that took the post and nothing else: every like of the posts pass raised a
TypeError instead of liking, and the author never reached the ledger.
"""

from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow import (
    PostUrlBusiness,
)
from taktik.core.social_media.instagram.workflows.core.ai_hooks import install_instagram_ai_hooks


class _Screenshot:
    size = (100, 200)

    def crop(self, box):
        return self

    def save(self, *_a, **_k):
        return None


class _Device:
    def screenshot(self):
        return _Screenshot()

    def xpath(self, _selector):
        return type("E", (), {"exists": False, "info": {}})()


class _AI:
    def __init__(self):
        self.analyses = 0

    def analyze_post(self, **_kwargs):
        self.analyses += 1
        return {"success": True}


def test_the_post_analysis_hook_keeps_the_author_of_the_like(monkeypatch):
    received = []
    monkeypatch.setattr(
        LikeOrchestration, "like_current_post",
        lambda self, record_as=None: received.append(record_as) or True,
    )
    monkeypatch.setattr(PostUrlBusiness, "in_thread_reply_writer", None, raising=False)
    ai = _AI()

    install_instagram_ai_hooks(
        ai=ai,
        ai_config={"postAnalysis": True, "smartComments": False},
        device=_Device(),
    )

    assert LikeOrchestration.like_current_post(object(), record_as="author_one") is True
    assert LikeOrchestration.like_current_post(object()) is True

    assert received == ["author_one", None]
    assert ai.analyses == 2
