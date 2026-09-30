"""A tap aimed at an element never lands on what the screen draws over it (`free_tap_zone`).

Android hands a touch to the element on top. On TikTok 43.1.4 the follow button covers the bottom of
the author's avatar (real capture `tests/unit/social_media/tiktok/fixtures/tt4314_fr_video_follow_over_avatar.xml`,
Pixel 3a: `yx4` [936,952][1057,1073], `hi1` [914,1027][1080,1122]): a tap sampled over the whole
avatar followed the author about one time in four. The bounds below are the ones of that capture.
"""

import random

from taktik.core.shared.behavior.tap import free_tap_zone, sample_tap_point

AVATAR = (936, 952, 1057, 1073)
FOLLOW = (914, 1027, 1080, 1122)

#: Every seed of the jitter played on the geometry alone: cheap, so many.
SEEDS = range(20000)


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


def test_the_whole_avatar_puts_taps_on_the_follow_button():
    """What the harvest did: the measure the fix is judged against."""
    on_follow = [seed for seed in SEEDS if _inside(sample_tap_point(AVATAR, rng=random.Random(seed)), FOLLOW)]

    assert len(on_follow) > len(SEEDS) // 10


def test_the_free_zone_is_the_avatar_above_the_follow_button():
    assert free_tap_zone(AVATAR, [FOLLOW]) == (936, 952, 1057, 1027)


def test_no_seed_lands_on_the_follow_button_and_every_seed_on_the_avatar():
    zone = free_tap_zone(AVATAR, [FOLLOW])

    for seed in SEEDS:
        tap = sample_tap_point(zone, rng=random.Random(seed))
        assert _inside(tap, AVATAR), (seed, tap)
        assert not _inside(tap, FOLLOW), (seed, tap)


def test_a_box_that_does_not_cross_the_target_changes_nothing():
    # Touching is not crossing: the bottom edge of a box is the first pixel below it.
    above = (936, 900, 1057, 952)
    assert free_tap_zone(AVATAR, [above]) == AVATAR
    assert free_tap_zone(AVATAR, []) == AVATAR


def test_a_row_keeps_the_largest_strip_the_button_leaves():
    # A list row with its button on the right: the name side is what is left.
    row = (0, 500, 1080, 650)
    button = (800, 540, 1040, 610)

    assert free_tap_zone(row, [button]) == (0, 500, 800, 650)


def test_a_covered_target_has_no_zone():
    wrapper = (914, 933, 1080, 1093)

    assert free_tap_zone(AVATAR, [wrapper]) is None


def test_a_sliver_is_not_a_zone():
    # The button leaves 5 % of the avatar's height: too little to aim at.
    low_follow = (914, 958, 1080, 1122)

    assert free_tap_zone(AVATAR, [low_follow]) is None
