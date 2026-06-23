"""OCR sanity actions for the Cartography Lab.

Lets a tester verify the shared OCR primitive in isolation BEFORE debugging why an
OCR-driven tap (notifications '… more', bio '… plus') missed: is tesseract bundled /
found on this host (``ocr.available``), and does an end-to-end screenshot→locate work
on the current screen (``ocr.locate``). Platform-agnostic primitive in
``taktik/core/shared/vision``.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("ocr.available")
def ocr_available(a, p):
    """Is OCR usable on this host? (pytesseract import AND the tesseract binary resolve.)
    No device screen needed. Guards every OCR-driven action."""
    from taktik.core.shared.vision import OcrService
    available = OcrService.available()
    logger.info(f"ocr.available: {available}")
    return {"success": bool(available),
            "message": "tesseract OCR is available" if available
                       else "OCR unavailable (tesseract binary / pytesseract not found)"}


@action("ocr.locate")
def ocr_locate(a, p):
    """End-to-end OCR sanity: screenshot the current screen and locate ``queries``.

    Params:
      - queries: comma-separated words to find (default 'more,suite,plus').
      - region: optional 'x1,y1,x2,y2' to limit OCR to a crop.
    Returns the count + each match's word/center/confidence.
    """
    from taktik.core.shared.vision import locate_text_on_screen

    raw_queries = (p.get("queries") or "more,suite,plus").strip()
    queries = [q.strip() for q in raw_queries.split(",") if q.strip()]
    region = None
    raw_region = (p.get("region") or "").strip()
    if raw_region:
        try:
            nums = [int(n) for n in raw_region.replace(" ", "").split(",")]
            if len(nums) == 4:
                region = tuple(nums)
        except ValueError:
            return {"success": False, "message": "region must be 'x1,y1,x2,y2'"}

    matches = locate_text_on_screen(a.device, queries, region=region)
    details = [{"text": m.text, "center": m.center, "confidence": round(m.confidence)} for m in matches]
    msg = f"ocr.locate: {len(matches)} match(es) for {queries}" + (f" in {region}" if region else "")
    logger.info(msg)
    return {"success": bool(matches), "count": len(matches), "matches": details, "message": msg}
