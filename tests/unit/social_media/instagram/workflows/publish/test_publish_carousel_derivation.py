"""Several media on a feed post must be published as a carousel.

Device report (2026-07-26): a run with three images pushed all three to the gallery, then took
the single-media branch and published only the first. The bot had been handed
`postType: "post"` with three `mediaPaths` -- the caller sent every path but never changed the
type. Nothing about that looks like a failure, so the run reported success.

The desktop app derives the type as well; this is pinned in the one launcher
(`run_instagram_publish`, `published_kind`), which the bridge, the CLI and the Lab all call: none
of them depends on its caller getting it right.
"""
import pytest

from taktik.core.social_media.instagram.workflows.publish.payload import (
    publish_request_from_payload,
    published_kind,
)


def _kind(payload):
    return published_kind(publish_request_from_payload(payload))


def test_several_media_on_a_post_becomes_a_carousel():
    assert _kind({"postType": "post", "mediaPaths": ["a.png", "b.png", "c.png"]}) == "carousel"


def test_a_single_medium_stays_a_post():
    assert _kind({"postType": "post", "mediaPaths": ["a.png"]}) == "post"


def test_an_explicit_carousel_is_untouched():
    assert _kind({"postType": "carousel", "mediaPaths": ["a.png", "b.png"]}) == "carousel"


@pytest.mark.parametrize("post_type", ["reel", "story"])
def test_reel_and_story_are_never_reinterpreted(post_type):
    """Both carry one medium by definition; a stray extra path must not turn them into a post."""
    assert _kind({"postType": post_type, "mediaPaths": ["a.mp4", "b.mp4"]}) == post_type


def test_the_launcher_publishes_the_derived_kind():
    from taktik.core.social_media.instagram.workflows.publish.agent_handler import run_instagram_publish

    built = {}

    class Post:
        def __init__(self, device, device_id, **kwargs):
            built.update(kwargs)

        def execute(self, **kwargs):
            return {"success": True}

    run_instagram_publish({"postType": "post", "mediaPaths": ["a.png", "b.png"]}, device_id="d",
                          connect=lambda: object(), workflow_factory=Post)

    assert built["post_type"] == "carousel"
