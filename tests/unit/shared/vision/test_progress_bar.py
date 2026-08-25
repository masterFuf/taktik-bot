"""The story progress bar is only readable as pixels on IG 442 — these lock its reading.

Geometry mirrors a real capture: a 1080-wide screen, a 4px bar at y 211-215 inset by 15px,
segments separated by a ~5px gap. Both backgrounds are real cases seen on device: a dark
scrim, and a bright photo with no scrim at all.
"""

from PIL import Image, ImageDraw

from taktik.core.shared.vision.progress_bar import count_progress_segments, segment_spans

BOUNDS = (0, 211, 1080, 215)
LEFT, RIGHT, TOP, BOTTOM = 15, 1065, 211, 215
GAP = 5


def _screen(background):
    return Image.new("RGB", (1080, 800), (background,) * 3)


def _draw_bar(image, segments, *, filled=255, unfilled=None, played=0):
    """Draw ``segments`` equal segments; the first ``played`` are fully filled.

    ``unfilled`` is the not-yet-played shade. On a device it is white composited over the
    media, so it is always BRIGHTER than the background — never darker.
    """
    draw = ImageDraw.Draw(image)
    span = (RIGHT - LEFT - GAP * (segments - 1)) / segments
    x = float(LEFT)
    for index in range(segments):
        shade = filled if index < played or unfilled is None else unfilled
        draw.rectangle([round(x), TOP, round(x + span), BOTTOM - 1], fill=(shade,) * 3)
        x += span + GAP
    return image


def test_counts_each_segment_on_a_dark_story():
    for segments in range(1, 7):
        image = _draw_bar(_screen(10), segments)
        assert count_progress_segments(image, BOUNDS) == segments


def test_counts_each_segment_on_a_bright_story():
    # No dark scrim: the bar sits on a light photo, which is what broke absolute thresholds.
    for segments in range(1, 7):
        image = _draw_bar(_screen(200), segments)
        assert count_progress_segments(image, BOUNDS) == segments


def test_a_half_played_segment_is_still_one_segment():
    # The played/unplayed boundary inside a segment must not be read as a separator.
    image = _draw_bar(_screen(200), 3, unfilled=222, played=1)
    assert count_progress_segments(image, BOUNDS) == 3


def test_no_bar_reads_as_unknown():
    assert count_progress_segments(_screen(200), BOUNDS) == 0
    assert count_progress_segments(_screen(10), BOUNDS) == 0


def test_uneven_widths_read_as_unknown_rather_than_a_guess():
    # Segments are laid out by an even weight, so anything else is not the bar.
    image = _screen(10)
    draw = ImageDraw.Draw(image)
    draw.rectangle([LEFT, TOP, 300, BOTTOM - 1], fill=(255,) * 3)
    draw.rectangle([320, TOP, RIGHT, BOTTOM - 1], fill=(255,) * 3)
    assert count_progress_segments(image, BOUNDS) == 0


def test_a_partial_stripe_reads_as_unknown():
    # Uniform width but covering a fraction of the bar: a highlight in the media, not the bar.
    image = _screen(10)
    ImageDraw.Draw(image).rectangle([LEFT, TOP, LEFT + 80, BOTTOM - 1], fill=(255,) * 3)
    assert count_progress_segments(image, BOUNDS) == 0


def test_unreadable_inputs_never_raise():
    image = _draw_bar(_screen(10), 3)
    assert count_progress_segments(None, BOUNDS) == 0
    assert count_progress_segments(image, (0, 211, 5000, 215)) == 0
    assert count_progress_segments(image, (0, 211, 0, 215)) == 0
    assert count_progress_segments(image, ("a", "b", "c", "d")) == 0
    assert count_progress_segments(image, (0, 0, 1080, 4)) == 0  # no room above the bar


def test_scaled_capture_maps_its_coordinates():
    image = _draw_bar(_screen(10), 4).resize((2160, 1600))
    # Without source_width the bounds land on the wrong rows entirely.
    assert count_progress_segments(image, BOUNDS) == 0
    assert count_progress_segments(image, BOUNDS, source_width=1080) == 4


def test_a_downscaled_capture_says_unknown_rather_than_a_wrong_count():
    # Halving the capture blurs the separators away. Answering "3 of the 4 stories" would be
    # worse than answering nothing, so the uniformity check must reject the reading.
    image = _draw_bar(_screen(10), 4).resize((540, 400))
    assert count_progress_segments(image, BOUNDS, source_width=1080) == 0


def test_spans_are_returned_left_to_right():
    spans = segment_spans(_draw_bar(_screen(10), 4), BOUNDS)
    assert len(spans) == 4
    assert [start for start, _ in spans] == sorted(start for start, _ in spans)
