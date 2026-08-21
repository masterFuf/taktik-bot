"""Reading the collected ads — the AI pass, deliberately OUT of any run.

Capture happens on the phone, at the speed of a flick. Reading happens here, later, on a
machine that has nothing else to do: an ad the model spends four seconds on must never be
four seconds a device spends standing still on the feed with an ad on screen.

It analyses CREATIVES, not sightings. `pending_analysis()` returns one row per creative and
orders them by `times_seen`, so a budget limited to twenty calls spends them on the twenty
ads that are actually running rather than on twenty one-off impressions. That ordering is
the whole reason the corpus deduplicates at capture time.

Every creative is stamped once analysed — including when the model could not read it — so a
picture that will never parse is not paid for on every pass.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from loguru import logger

from taktik.core.app.ai.spend import AI_SPEND_AD

log = logger.bind(module="instagram-ad-analysis")

_SYSTEM_PROMPT = (
    "You analyse advertising creatives for competitive research. "
    "You are shown ONE ad exactly as it appeared in an Instagram feed. "
    "Describe what the advertiser is doing, factually and briefly. "
    "Answer with JSON only."
)

_USER_PROMPT = (
    "Read this ad and return JSON with these keys:\n"
    '  "angle": the marketing angle in one short sentence\n'
    '  "promise": the main promise made to the reader\n'
    '  "offer": the concrete offer, if any (discount, free trial, lead magnet…)\n'
    '  "target": who it visibly speaks to\n'
    '  "format": photo | video | carousel | unclear\n'
    '  "cta": the call to action shown\n'
    '  "language": ISO code of the ad copy\n'
    "Use null for anything the creative does not show. Do not invent a brand or a price."
)


def _write_temp_jpeg(blob: bytes) -> Optional[str]:
    """The vision API takes a path; the corpus stores a blob."""
    try:
        handle, path = tempfile.mkstemp(suffix=".jpg", prefix="taktik_ad_")
        with os.fdopen(handle, "wb") as stream:
            stream.write(blob)
        return path
    except Exception as exc:
        log.debug(f"Could not materialise the creative: {exc}")
        return None


def analyze_pending_ads(ai_service, *, limit: int = 20,
                        platform: str = "instagram") -> Dict[str, Any]:
    """Analyse up to `limit` creatives that have never been read. Returns a small report.

    `ai_service` is the same `AIService` every other AI path uses, so the model choice, the
    cost accounting and the truncation retry are shared rather than re-implemented here.
    """
    from taktik.core.database.instagram_feed_ads import InstagramFeedAdsService

    report = {"analyzed": 0, "failed": 0, "skipped": 0, "creatives": []}
    if ai_service is None:
        log.warning("No AI service available — ad analysis skipped")
        report["skipped"] = limit
        return report

    pending: List[Dict[str, Any]] = InstagramFeedAdsService.pending_analysis(
        limit=limit, platform=platform,
    )
    if not pending:
        log.info("No creative waiting for analysis")
        return report

    log.info(f"Analysing {len(pending)} creative(s), most-seen first")

    for creative in pending:
        blob = creative.get("screenshot")
        if not blob:
            # No picture: stamp it anyway so it stops coming back as pending forever.
            InstagramFeedAdsService.save_analysis(creative["id"], {"notes": "no screenshot stored"})
            report["skipped"] += 1
            continue

        path = _write_temp_jpeg(blob)
        if not path:
            report["failed"] += 1
            continue

        try:
            context = ""
            if creative.get("advertiser"):
                context += f"\nAdvertiser account: @{creative['advertiser']}"
            if creative.get("ocr_text"):
                # The OCR text is a hint, not the truth: tesseract mangles stylised type, so
                # the model is told to trust its own reading of the picture over this.
                context += f"\nText our OCR read (may be imperfect): {creative['ocr_text'][:500]}"

            result = ai_service.vision_json_completion(
                _SYSTEM_PROMPT,
                _USER_PROMPT + context,
                path,
                label="ad_analysis",
                kind=AI_SPEND_AD,
            )
            payload = result.get("payload") if isinstance(result, dict) else None
            if payload:
                InstagramFeedAdsService.save_analysis(creative["id"], payload)
                report["analyzed"] += 1
                report["creatives"].append({
                    "id": creative["id"],
                    "advertiser": creative.get("advertiser"),
                    "times_seen": creative.get("times_seen"),
                    "angle": payload.get("angle"),
                })
                log.info(
                    f"Analysed @{creative.get('advertiser') or 'unknown'} "
                    f"({creative.get('times_seen')}x seen): {payload.get('angle')}"
                )
            else:
                report["failed"] += 1
                log.debug(f"Unusable answer for creative {creative['id']}: {result}")
        except Exception as exc:
            report["failed"] += 1
            log.debug(f"Ad analysis failed for {creative['id']}: {exc}")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    log.info(
        f"Ad analysis done: {report['analyzed']} analysed, "
        f"{report['failed']} failed, {report['skipped']} skipped"
    )
    return report


def analysis_summary(platform: str = "instagram") -> str:
    """One-line state of the corpus, for a CLI that just ran a pass."""
    from taktik.core.database.instagram_feed_ads import InstagramFeedAdsService

    top = InstagramFeedAdsService.top_creatives(limit=5, platform=platform)
    if not top:
        return "No ad collected yet."
    lines = [
        f"  {row['times_seen']:>4}x  @{row['advertiser'] or 'unknown'}  "
        f"{(json.loads(row['ai_analysis']).get('angle') if row.get('ai_analysis') else '') or ''}"
        for row in top
    ]
    return "Most-seen creatives:\n" + "\n".join(lines)


__all__ = ["analyze_pending_ads", "analysis_summary"]
