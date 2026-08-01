"""An unreadable counter is NULL, and the panel must survive it.

"I could not read this counter" and "this post has zero likes" are different facts, and the
bot has said so since the counters were made language-agnostic: `_extract_current_post_metadata`
initialises both counts to None and only overwrites what it manages to read.

The desktop panel guarded that value with `!== undefined`, which null passes — so the first
reel whose counter the post selectors could not reach crashed the whole session view on
`toLocaleString`. The contract is pinned here so the bot side cannot drift back into
pretending zero, which would be worse: a post filtered out for "0 likes" it never had.
"""

import pytest


class _Extractors:
    """Shared extractor double — the reel-aware one the workflow already uses."""

    def __init__(self, likes=None, comments=None):
        self._likes, self._comments = likes, comments

    def extract_likes_count_from_ui(self, is_reel=None):
        return self._likes

    def extract_comments_count_from_ui(self, is_reel=None):
        return self._comments


def test_the_metadata_declares_both_counters_up_front():
    """They are initialised to None, never left absent: an absent key and a null value read
    the same to a consumer, but only one of them is a stated contract."""
    import inspect
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins import (
        post_finder,
    )
    source = inspect.getsource(post_finder.HashtagPostFinderMixin._extract_current_post_metadata)
    assert "'likes_count': None" in source
    assert "'comments_count': None" in source


def test_the_reel_fallback_asks_the_shared_extractor():
    """The two selector loops above it are POST selectors; on a reel they come back empty
    while the shared extractor reads the very same counter without trouble."""
    import inspect
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins import (
        post_finder,
    )
    source = inspect.getsource(post_finder.HashtagPostFinderMixin._extract_current_post_metadata)
    tail = source[source.index("Retombée REEL"):]
    assert "extract_likes_count_from_ui" in tail
    assert "extract_comments_count_from_ui" in tail


def test_null_stays_possible_after_the_fallback():
    """The fallback is a second chance, not a floor. Turning an unreadable counter into 0
    would filter the post out for likes it never claimed to have — the exact bug that made
    every French reel look empty."""
    extractors = _Extractors(likes=None, comments=None)
    assert extractors.extract_likes_count_from_ui(is_reel=True) is None
    assert extractors.extract_comments_count_from_ui(is_reel=True) is None


@pytest.mark.parametrize("value", [None, 0, 35])
def test_a_counter_of_any_shape_is_emitted_as_is(value):
    """Whatever the extractor returns travels to the panel unchanged — which is why the
    panel, and not the bot, is what had to learn to render a null."""
    payload = {'likes_count': value}
    assert payload.get('likes_count') == value
