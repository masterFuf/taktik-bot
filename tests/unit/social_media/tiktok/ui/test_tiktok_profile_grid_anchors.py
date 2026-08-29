"""The profile post grid has to be findable on both shipped versions.

Measured 2026-08-29 on @zachking, a profile with thousands of videos:

    43.1.4   e52 -> 9,  cover-ancestor -> 9
    46.6.3   e52 -> 0,  cover-ancestor -> 9
    feed     e52 -> 0,  cover-ancestor -> 0

The middle line is the bug this locks down: on 46.6.3 the grid read zero, so the
workflow logged "no posts", emitted `no_posts` and left WITHOUT INTERACTING — on every
profile of that version. Nothing failed; the run just did nothing and said it was done.
"""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS

COVER_ANCHOR = '//*[contains(@resource-id, ":id/cover")]/ancestor::*[@clickable="true"][1]'


def test_the_grid_has_a_route_that_does_not_depend_on_a_build_id():
    """`e52` is a 43.1.4 build id. A catalogue holding only build ids dies at the next
    version bump, silently, with the workflow reporting success."""
    assert COVER_ANCHOR in FOLLOWERS_SELECTORS.profile_post_item


def test_the_first_post_uses_the_same_route():
    assert f'({COVER_ANCHOR})[1]' in FOLLOWERS_SELECTORS.first_post


def test_the_legacy_id_is_kept_and_kept_first():
    """It is right on the version that shipped it, and it is the cheapest match there.
    Dropping it would trade one broken version for another."""
    assert FOLLOWERS_SELECTORS.profile_post_item[0].endswith('[@clickable="true"]')
    assert ':id/e52' in FOLLOWERS_SELECTORS.profile_post_item[0]


def test_the_thumbnail_itself_is_not_the_tap_target():
    """The `cover` ImageView is clickable=false; tapping it does nothing. The route has to
    climb to the nearest clickable ancestor, which is what the axis is for."""
    for selector in FOLLOWERS_SELECTORS.profile_post_item + FOLLOWERS_SELECTORS.first_post:
        if ':id/cover' in selector:
            assert 'ancestor::*[@clickable="true"][1]' in selector
