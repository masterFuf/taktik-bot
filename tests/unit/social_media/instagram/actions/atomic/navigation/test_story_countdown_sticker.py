"""Story advance must not tap an interactive sticker (countdown, poll…).

Real device case (2026-07-05): tapping the countdown sticker opened the countdown consumption
sheet, which blocks the story flow. The advance tap zone is steered around such stickers, and the
sheet is registered as a blocking modal so it's recovered from if it still opens.
"""

from taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation import (
    _safe_story_advance_zone,
)
from taktik.core.social_media.instagram.ui.selectors.support.blocking_modals import (
    BLOCKING_MODAL_SELECTORS,
)


def _overlaps(zone, sticker):
    zx0, zy0, zx1, zy1 = zone
    return not (
        zx1 <= sticker["left"] or zx0 >= sticker["right"]
        or zy1 <= sticker["top"] or zy0 >= sticker["bottom"]
    )


def test_no_sticker_returns_the_default_right_band():
    z = _safe_story_advance_zone(1080, 2400, None)
    assert z == (int(1080 * 0.62), int(2400 * 0.30), int(1080 * 0.88), int(2400 * 0.70))


def test_real_countdown_sticker_is_avoided():
    # Exact sticker bounds from the device dump.
    sticker = {"left": 166, "top": 900, "right": 914, "bottom": 1405}
    z = _safe_story_advance_zone(1080, 2400, sticker)
    assert not _overlaps(z, sticker), f"advance zone {z} overlaps the countdown sticker"
    # And it stays a usable band.
    assert z[2] > z[0] and z[3] > z[1]


def test_sticker_outside_the_band_keeps_default_zone():
    # A sticker high up (above the 0.30h band) doesn't force a change.
    sticker = {"left": 200, "top": 100, "right": 900, "bottom": 400}
    z = _safe_story_advance_zone(1080, 2400, sticker)
    assert z == (int(1080 * 0.62), int(2400 * 0.30), int(1080 * 0.88), int(2400 * 0.70))
    assert not _overlaps(z, sticker)


def test_sticker_filling_the_band_falls_back_to_the_right_or_corner():
    # A big sticker covering the whole mid band on the left/centre -> tap to its right or a corner,
    # never on it.
    sticker = {"left": 0, "top": 600, "right": 760, "bottom": 1800}
    z = _safe_story_advance_zone(1080, 2400, sticker)
    assert not _overlaps(z, sticker)


def test_countdown_sheet_is_a_registered_blocking_modal():
    combined = BLOCKING_MODAL_SELECTORS.combined_xpath()
    assert "countdown_consumption_sheet_container" in combined
    # It resolves to its own signature name (used for logging / recovery).
    assert BLOCKING_MODAL_SELECTORS.identify(
        lambda q: "countdown_consumption_sheet_container" in q
    ) == "countdown_consumption_sheet"
