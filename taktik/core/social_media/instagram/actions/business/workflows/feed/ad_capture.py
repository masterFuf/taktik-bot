"""Capturing the sponsored posts a feed run glides past.

The crawl has always recognised ads in order to SKIP them, and threw the recognition away.
This turns that into a corpus: at the exact moment the crawl says "this is an ad", the ad is
on screen with a fresh dump, and the very next thing it does is flick past it. That instant
is the only capture window there is.

What is kept: a screenshot cropped to the ad, the advertiser account, the visible text (local
OCR, no API), and a perceptual fingerprint. The fingerprint is the dedup key, so a creative
met forty times is one row with `times_seen = 40` rather than forty rows.

Deliberately NOT done: opening the ad. Tapping it would signal interest to the ranking, cost
time, and is not needed for the read that matters (who keeps spending, on what angle).
"""

from __future__ import annotations

import io
from typing import Any, Callable, Dict, Optional

from loguru import logger

log = logger.bind(module="instagram-ad-capture")

# The stored screenshot is for reading an ad back, not for archiving pixels. Downscaling the
# long edge keeps the blob small — this table lives next to a database that already carries
# profile pictures, and a corpus is meant to grow for months.
_MAX_EDGE = 900
_JPEG_QUALITY = 80


def _crop_to_ad(image, anchors: Dict[str, Any], screen_height: int):
    """Crop the screenshot to the ad unit, using the markers the crawl already computed.

    `ad_tops` holds the y of each sponsored marker; the dominant one is the ad we are about
    to skip. We keep from just above that marker to the bottom of the screen, which is where
    the creative and its caption sit. Falls back to the full screenshot when the geometry
    cannot be read — a slightly wider picture is worth more than no picture.
    """
    try:
        ad_tops = [y for y in (anchors.get("ad_tops") or []) if isinstance(y, int)]
        if not ad_tops:
            return image
        top = max(0, min(ad_tops) - int(0.02 * screen_height))
        width, height = image.size
        # The dump's coordinates are in device pixels; the screenshot may differ in scale.
        scale = height / float(screen_height or height)
        top_px = int(top * scale)
        if top_px >= height - 10:
            return image
        return image.crop((0, top_px, width, height))
    except Exception as exc:
        log.debug(f"Ad crop failed, keeping the full frame: {exc}")
        return image


def _encode(image) -> Optional[bytes]:
    """Downscale + JPEG-encode, or ``None``."""
    try:
        width, height = image.size
        longest = max(width, height)
        if longest > _MAX_EDGE:
            ratio = _MAX_EDGE / float(longest)
            image = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return buffer.getvalue()
    except Exception as exc:
        log.debug(f"Could not encode ad screenshot: {exc}")
        return None


def _advertiser_from(anchors: Dict[str, Any]) -> Optional[str]:
    """The account behind the dominant unit, as the crawl already read it."""
    posts = anchors.get("posts") or []
    if not posts:
        return None
    try:
        return posts[0][1] or None
    except (IndexError, TypeError):
        return None


def make_ad_capturer(device, *, account_id: Optional[int] = None,
                     read_text: bool = True) -> Callable[[Dict[str, Any]], None]:
    """Build the `on_ad` callback the feed crawl calls while an ad is on screen.

    The crawl stays dumb: it reports "an ad, now", and this decides what to do with it. The
    callback swallows everything — collecting market intelligence is a side effect of a run
    and must never be able to cost the run it rides in on.
    """

    def capture(anchors: Dict[str, Any]) -> None:
        try:
            from taktik.core.database.instagram_feed_ads import InstagramFeedAdsService
            from taktik.core.shared.vision.fingerprint import dhash

            image = device.screenshot_pil()
            if image is None:
                return

            try:
                screen_height = device.get_screen_size()[1]
            except Exception:
                screen_height = image.size[1]

            cropped = _crop_to_ad(image, anchors, screen_height)
            creative_hash = dhash(cropped)
            if not creative_hash:
                return

            ocr_text = None
            if read_text:
                try:
                    from taktik.core.shared.vision.ocr import OcrService

                    # The copy is baked INTO the creative — no UI dump reaches it, which is
                    # exactly why this is worth an OCR pass. Degrades to "" without
                    # tesseract, and an ad with no legible text is a normal outcome.
                    ocr_text = OcrService.read_text(cropped) or None
                except Exception as exc:
                    log.debug(f"OCR skipped for this ad: {exc}")

            InstagramFeedAdsService.record_sighting(
                creative_hash=creative_hash,
                advertiser=_advertiser_from(anchors),
                account_id=account_id,
                screenshot=_encode(cropped),
                ocr_text=ocr_text,
            )
            log.debug(f"Ad captured ({creative_hash}) from @{_advertiser_from(anchors)}")
        except Exception as exc:
            log.debug(f"Ad capture skipped: {exc}")

    return capture
