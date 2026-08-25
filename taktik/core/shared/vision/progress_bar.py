"""Read a segmented progress bar from PIXELS, when the accessibility tree cannot.

Instagram 442 draws the story-viewer progress bar in Compose: a SINGLE node
(`reel_viewer_progress_bar`) with no children and no content-desc, whatever the number of
stories. The a11y tree therefore cannot say whether a user posted one story or nine — the
segments exist only as drawn pixels. Counting the nodes (the pre-442 way) silently returns
1 for everyone.

The bar is an OVERLAY: on the row that crosses it, a bar pixel is brighter than the same
column just above and just below it, while an inter-segment gap shows the media underneath
and matches its vertical neighbours. Comparing a column to its own neighbourhood — instead
of thresholding absolute luminance — is what makes this work on a dark story and on a
white one alike (both verified on device).

Pure function: takes a PIL image and the bounds of the bar, returns a count. No device, no
platform knowledge, so a TikTok/YouTube surface with the same drawing can reuse it.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from loguru import logger

log = logger.bind(module="vision-progress-bar")

# A run narrower than this is anti-aliasing or JPEG ringing, not a segment.
_MIN_SEGMENT_PX = 8
# A bar pixel must beat BOTH vertical neighbours by this much (0-255 luminance).
_MIN_CONTRAST = 10
# Segments are laid out by an even weight, so real ones are near-equal. A spread wider than
# this means we read something else (a photo edge, a banner) — better to admit we do not know.
_MAX_WIDTH_SPREAD = 0.25
# The segments together must cover most of the bar; otherwise we matched noise.
_MIN_COVERAGE = 0.6


def _luminance_row(pixels, y: int, left: int, right: int) -> list:
    return [sum(pixels[x, y]) / 3 for x in range(left, right)]


def segment_spans(
    image,
    bounds: Sequence[int],
    *,
    source_width: Optional[int] = None,
) -> list:
    """The (start, width) of every segment drawn inside ``bounds``, left to right.

    ``bounds`` is ``(left, top, right, bottom)`` in the coordinate space of ``source_width``
    (the device screen when it is given, the image itself otherwise).
    """
    try:
        left, top, right, bottom = (int(v) for v in bounds)
    except (TypeError, ValueError):
        return []

    if source_width and source_width > 0 and image.width != source_width:
        scale = image.width / source_width
        left, top, right, bottom = (int(v * scale) for v in (left, top, right, bottom))

    if right <= left or bottom <= top or right > image.width or bottom >= image.height:
        return []

    # One row inside the bar, one clear of it on each side. The bar is only a few pixels
    # tall, so the neighbours stay close enough that the media behind them is the same.
    gap = max(3, bottom - top)
    inside = (top + bottom) // 2
    above = max(0, top - gap)
    below = min(image.height - 1, bottom + gap)
    if above == inside or below == inside:
        return []

    pixels = image.convert("RGB").load()
    row = _luminance_row(pixels, inside, left, right)
    up = _luminance_row(pixels, above, left, right)
    down = _luminance_row(pixels, below, left, right)

    spans: list = []
    start = 0
    width = 0
    for index, value in enumerate(row):
        # Brighter than BOTH neighbours: an edge in the media itself only beats one of them.
        if value - max(up[index], down[index]) > _MIN_CONTRAST:
            if not width:
                start = index
            width += 1
        elif width:
            spans.append((start, width))
            width = 0
    if width:
        spans.append((start, width))

    return [span for span in spans if span[1] >= _MIN_SEGMENT_PX]


def count_progress_segments(
    image,
    bounds: Sequence[int],
    *,
    source_width: Optional[int] = None,
) -> int:
    """How many segments the bar is split into, or 0 when the reading is not trustworthy.

    0 means UNKNOWN, never "none": callers must keep whatever they already had rather than
    record a fabricated count.
    """
    if image is None:
        return 0

    try:
        spans = segment_spans(image, bounds, source_width=source_width)
    except Exception as exc:  # a malformed image must never break a workflow
        log.debug(f"progress-bar read failed: {exc}")
        return 0

    if not spans:
        return 0

    widths = sorted(width for _, width in spans)
    median = widths[len(widths) // 2]
    if median <= 0:
        return 0
    if any(abs(width - median) > median * _MAX_WIDTH_SPREAD for width in widths):
        log.debug(f"progress-bar widths not uniform ({widths}) -> unknown")
        return 0

    bar_width = int(bounds[2]) - int(bounds[0])
    if source_width and source_width > 0 and image.width != source_width:
        bar_width = int(bar_width * image.width / source_width)
    if bar_width > 0 and sum(widths) < bar_width * _MIN_COVERAGE:
        log.debug(f"progress-bar coverage too low ({sum(widths)}/{bar_width}) -> unknown")
        return 0

    return len(spans)
