"""Humanised profile-grid entry planning — the bot must not always open the
top-left (newest) post, and must adapt scrolling to how many posts exist.

This is the "open post / grid scroll" entry half of the Profile humanisation work
(`taktik-docs/bot/security/humanization-master-plan.md`, §3.3 + §7 checklist). The
*where/how to enter* logic is here, pure and testable offline; the device
execution (real thumbnails + human gesture) lives in the like workflow.
"""

import random

from taktik.core.shared.behavior.grid_entry import (
    GRID_COLUMNS,
    plan_prescroll,
    sample_entry_index,
    row_weights,
    _NO_SCROLL_MAX_POSTS,
    _MAX_PRESCROLL,
)


# ── sample_entry_index ───────────────────────────────────────────────────────

def test_index_always_in_range():
    rng = random.Random(7)
    for visible in range(1, 30):
        for _ in range(200):
            idx = sample_entry_index(visible, rng=rng)
            assert 0 <= idx < visible


def test_single_thumbnail_is_index_zero():
    assert sample_entry_index(1) == 0
    assert sample_entry_index(0) == 0


def test_not_always_top_left():
    """The exact top-left cell (index 0) must NOT be a near-constant — that is the
    very fingerprint we are removing."""
    rng = random.Random(123)
    picks = [sample_entry_index(6, rng=rng) for _ in range(2000)]
    zero_share = picks.count(0) / len(picks)
    # index 0 is one of three top-row cells: it should be common but far from constant.
    assert 0.10 < zero_share < 0.45
    assert len(set(picks)) >= 4  # genuinely spread across the grid


def test_weighted_toward_top_rows():
    """Top row should be opened more often than deeper rows (natural), without the
    deeper rows ever being impossible."""
    rng = random.Random(99)
    picks = [sample_entry_index(9, rng=rng) for _ in range(3000)]
    top_row = sum(1 for p in picks if p // GRID_COLUMNS == 0)
    last_row = sum(1 for p in picks if p // GRID_COLUMNS == 2)
    assert top_row > last_row
    assert last_row > 0  # deeper posts still reachable


def test_row_weights_monotonic_non_increasing():
    w = row_weights(9)
    # weight per row must not increase as we go down the grid
    assert w[0] >= w[GRID_COLUMNS] >= w[2 * GRID_COLUMNS]
    # within a row the weight is flat (uniform across columns)
    assert w[0] == w[1] == w[2]


# ── plan_prescroll ───────────────────────────────────────────────────────────

def test_no_prescroll_on_small_profiles():
    rng = random.Random(5)
    for posts in range(0, _NO_SCROLL_MAX_POSTS + 1):
        for _ in range(50):
            assert plan_prescroll(posts, rng=rng) == 0


def test_prescroll_within_cap():
    rng = random.Random(11)
    for posts in (20, 56, 200, 5000):
        for _ in range(500):
            n = plan_prescroll(posts, rng=rng)
            assert 0 <= n <= _MAX_PRESCROLL


def test_prescroll_capped_by_available_posts():
    """A profile just over the no-scroll threshold has at most one extra screen,
    so we never plan more scrolls than there are posts to reveal."""
    rng = random.Random(3)
    seen = {plan_prescroll(14, rng=rng) for _ in range(500)}
    # 14 posts: (14-6)//9 = 0 useful screens → never scroll (cap collapses to 0).
    assert seen == {0}


def test_prescroll_sometimes_happens_on_large_profiles():
    rng = random.Random(42)
    counts = [plan_prescroll(500, rng=rng) for _ in range(1000)]
    nonzero = [c for c in counts if c > 0]
    assert len(nonzero) > 0  # large profiles do get scrolled sometimes
    # but most of the time we still open something on the first screen
    assert counts.count(0) > len(counts) * 0.4


def test_deterministic_with_seed():
    a = [plan_prescroll(300, rng=random.Random(1)) for _ in range(20)]
    b = [plan_prescroll(300, rng=random.Random(1)) for _ in range(20)]
    assert a == b
    c = [sample_entry_index(9, rng=random.Random(2)) for _ in range(20)]
    d = [sample_entry_index(9, rng=random.Random(2)) for _ in range(20)]
    assert c == d
