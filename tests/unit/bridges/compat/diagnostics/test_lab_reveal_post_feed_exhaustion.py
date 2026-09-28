"""`scroll.reveal_post` follows the production's reading of a feed of ads and suggested posts.

Measured on a Pixel 3a (Instagram 410, in English), Lab auto-test, 2026-09-28: the test account follows
few people, and its home feed serves long blocks of suggested posts and ads. `scroll.reveal_post` made
one production advance (`scroll_feed_to_next_post`), which stopped on a suggested post after its skip
budget (`filler_run`), and failed: the tests it prepares were "blocked", twice in one pass. The
production reading (`browse_feed`) takes one filler run for a normal block and advances again; only
`_TAIL_FILLER_RUNS` in a row make the followed feed exhausted.

The results the scroll hands back are the ones the phone gave (the Lab reports of that pass, cut to
the keys this action reads); the scroll itself is the production's, not played here.
"""

from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.compat.diagnostics.actions.instagram import register_actions as register_instagram
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import _TAIL_FILLER_RUNS

#: Report of `scroll.reveal_post`, Pixel 3a, 2026-09-28 23:16: stopped on a suggested post.
FILLER_RUN = {"on_feed": True, "filler_run": True, "is_suggested": True, "is_ad": False,
              "metadata_visible": False, "full_post": False, "suggested_skipped": 2, "ads_skipped": 0}
#: The same pass, the next advance that met a real post with its engagement bar.
REAL_POST = {"on_feed": True, "filler_run": False, "is_suggested": False, "is_ad": False,
             "metadata_visible": True, "full_post": True, "suggested_skipped": 0, "ads_skipped": 0}


class _Scroll:
    """The feed scroll as the action calls it: the current post not framed, then the results given."""

    def __init__(self, *results):
        self.results = list(results)
        self.advances = 0

    def _reveal_current_metadata(self):
        return False

    def _read_feed_anchors(self):
        return {"on_feed": True}

    def _metadata_visible(self, _anchors):
        return (False, None)

    def _dominant_is_ad(self, _anchors):
        return False

    def scroll_feed_to_next_post(self, skip_ads=True, skip_suggested=True):
        self.advances += 1
        return dict(self.results.pop(0))


class _Bundle:
    def __init__(self, scroll):
        self.scroll = scroll


def _reveal(*results):
    register_instagram()
    scroll = _Scroll(*results)
    return INSTAGRAM_ACTIONS["scroll.reveal_post"](_Bundle(scroll), {}), scroll


def test_one_block_of_suggested_posts_is_glided_past_to_the_real_post_behind_it():
    result, scroll = _reveal(FILLER_RUN, REAL_POST)
    assert result["success"] is True
    assert scroll.advances == 2


def test_a_feed_of_nothing_but_filler_is_declared_not_applicable_as_the_production_calls_it_exhausted():
    result, scroll = _reveal(*[FILLER_RUN] * _TAIL_FILLER_RUNS)
    assert result["success"] is False
    assert "the feed served only ads and suggested posts" in result["details"]["not_applicable"]
    assert scroll.advances == _TAIL_FILLER_RUNS


def test_off_the_feed_it_stays_a_failure():
    result, _scroll = _reveal({**FILLER_RUN, "on_feed": False, "filler_run": False})
    assert result["success"] is False
    assert "not_applicable" not in (result.get("details") or {})
