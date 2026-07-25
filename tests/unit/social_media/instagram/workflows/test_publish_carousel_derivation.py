"""Several media on a feed post must be published as a carousel.

Device report (2026-07-26): a run with three images pushed all three to the gallery, then took
the single-media branch and published only the first. The bot had been handed
`postType: "post"` with three `mediaPaths` — the caller sent every path but never changed the
type. Nothing about that looks like a failure, so the run reported success.

The desktop app derives the type as well; this is pinned here because the bridge is a public
entry point and must not depend on its caller getting it right.
"""
import pytest

from bridges.instagram.publish.runtime.bridge import InstagramPublishBridge


def _bridge(config):
    # __init__ installs signal handlers, which only works on the main thread; pytest runs there.
    return InstagramPublishBridge(config)


def test_several_media_on_a_post_becomes_a_carousel():
    bridge = _bridge({
        "deviceId": "9CHAY1PNRW",
        "postType": "post",
        "mediaPaths": ["a.png", "b.png", "c.png"],
    })
    assert bridge.post_type == "carousel"


def test_a_single_medium_stays_a_post():
    bridge = _bridge({"deviceId": "d", "postType": "post", "mediaPaths": ["a.png"]})
    assert bridge.post_type == "post"


def test_an_explicit_carousel_is_untouched():
    bridge = _bridge({"deviceId": "d", "postType": "carousel", "mediaPaths": ["a.png", "b.png"]})
    assert bridge.post_type == "carousel"


@pytest.mark.parametrize("post_type", ["reel", "story"])
def test_reel_and_story_are_never_reinterpreted(post_type):
    """Both carry one medium by definition; a stray extra path must not turn them into a post."""
    bridge = _bridge({
        "deviceId": "d",
        "postType": post_type,
        "mediaPaths": ["a.mp4", "b.mp4"],
    })
    assert bridge.post_type == post_type
