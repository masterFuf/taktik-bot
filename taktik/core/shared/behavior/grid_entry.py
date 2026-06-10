"""Humanised profile-grid entry planning (pure, no device I/O).

A human visiting a profile to engage does NOT always open the top-left (newest)
post — yet the like workflow historically always opened `posts[0]`, a trivially
fingerprintable constant entry point. This module decides, from the profile's
post count and the number of grid thumbnails currently rendered, HOW to enter:

  1. optionally pre-scroll the grid a few times first (only on profiles large
     enough that scrolling looks natural — never on a 6-post profile), then
  2. which *visible* thumbnail to open — weighted toward the top rows (where a
     curious visitor naturally starts) but spread, so the exact top-left cell is
     just one option among many, never a constant.

Pure functions + a tiny dataclass; the workflow executes the plan with the real
grid selectors and the shared human gesture/tap primitives. Lives in
`shared/behavior` as a humanisation contract — platform-agnostic, no
`social_media` imports — and takes an injectable `rng` so a seeded session is
reproducible (cf. the master plan's seeded-RNG goal).
"""

from __future__ import annotations

import random
from typing import Optional, Sequence

# Instagram (and most grids) render 3 columns.
GRID_COLUMNS = 3

# A first profile screen exposes ~2 full rows + a partial one before any scroll.
_VISIBLE_FIRST_SCREEN = 6
# Each grid pre-scroll (~one screen flick) reveals roughly this many more posts.
_POSTS_PER_SCREEN = 9

# At/under this many posts, everything already fits (or nearly), so scrolling the
# grid before opening a post looks forced — never pre-scroll.
_NO_SCROLL_MAX_POSTS = 12
# On a large-enough profile, probability we pre-scroll the grid at all.
_PRESCROLL_PROB = 0.45
# Hard cap on grid pre-scrolls. A visitor browses a little; they don't doomscroll
# the grid before opening something.
_MAX_PRESCROLL = 3
# Bias the pre-scroll count toward fewer scrolls.
_PRESCROLL_DECAY = 0.5

# How quickly the per-row weight decays as we go down the grid. Row 0 (the newest
# / top row) is the most likely; deeper rows stay possible but rarer. Tuned so the
# top row is favoured without the exact top-left ever being a near-certainty.
_ROW_DECAY = 0.55


def plan_prescroll(posts_count: int, *, rng: Optional[random.Random] = None) -> int:
    """How many times to human-scroll the grid down before opening a post.

    Returns 0 on small profiles (scrolling would look forced) or when the dice
    say "open something on the first screen". Otherwise a small count, capped both
    by `_MAX_PRESCROLL` and by how many screens of posts actually exist (so we
    never scroll into empty space below the grid).
    """
    rng = rng or random
    if posts_count <= _NO_SCROLL_MAX_POSTS:
        return 0
    if rng.random() >= _PRESCROLL_PROB:
        return 0
    max_useful = max(0, (posts_count - _VISIBLE_FIRST_SCREEN) // _POSTS_PER_SCREEN)
    cap = min(_MAX_PRESCROLL, max_useful)
    if cap <= 0:
        return 0
    choices = list(range(1, cap + 1))
    weights = [_PRESCROLL_DECAY ** (n - 1) for n in choices]
    return rng.choices(choices, weights=weights)[0]


def sample_entry_index(visible_count: int, *, rng: Optional[random.Random] = None) -> int:
    """Pick which of the currently visible thumbnails to open.

    Weighted toward the top rows (a visitor's eye starts there) but spread across
    the row and into deeper rows, so the opened post varies every run and the
    exact top-left cell is never a constant. `visible_count` is the number of grid
    thumbnails rendered *right now* (after any pre-scroll).
    """
    if visible_count <= 1:
        return 0
    rng = rng or random
    weights = [_ROW_DECAY ** (i // GRID_COLUMNS) for i in range(visible_count)]
    return rng.choices(range(visible_count), weights=weights)[0]


def row_weights(visible_count: int) -> Sequence[float]:
    """Expose the per-thumbnail weights (for tests / Lab introspection)."""
    return [_ROW_DECAY ** (i // GRID_COLUMNS) for i in range(max(0, visible_count))]
