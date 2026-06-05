"""Scroll actions for Instagram compat diagnostics."""

from bridges.compat.diagnostics.actions.instagram import action


@action("scroll.up")
def scroll_up(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_up(scale=scale)
    return True


@action("scroll.down")
def scroll_down(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_down(scale=scale)
    return True


@action("scroll.feed_next")
def scroll_feed_next(a, p):
    """ONE decisive human gesture to reveal the next post (flick / continuous drag / rare skim),
    real OS fling coast — not a burst of mini-scrolls. One dump measures the landing; one nudge
    if the post lands low. Surface-safe (never taps a reel/link/story); recovers if off-feed."""
    skip_ads = str(p.get("skip_ads", "1")).lower() not in ("0", "false", "no")
    skip_sugg = str(p.get("skip_suggested", "1")).lower() not in ("0", "false", "no")
    res = a.scroll.scroll_feed_to_next_post(skip_ads=skip_ads, skip_suggested=skip_sugg)
    g, d = res.get("gestures"), res.get("dumps")
    mode, land, corr = res.get("mode"), res.get("land_ratio"), res.get("corrected")
    full, meta = res.get("full_post"), res.get("metadata_visible")
    if not res.get("on_feed"):
        msg = f"hors feed (surface={res.get('surface')}) — recuperation echouee"
        if res.get("error"):
            msg = f"erreur scroll: {res['error']}"
        return {"success": False, "message": msg, "details": res}
    rev = res.get("reveal") or 0
    pub = res.get("ads_skipped") or 0
    sug = res.get("suggested_skipped") or 0
    stuck = res.get("stuck_retry") or 0
    tail = (f"land={land}" + (" +1 correction" if corr else "") + (f" +{rev} reveal" if rev else "")
            + (f" +{stuck} retry(bloque)" if stuck else "")
            + (f" ({pub} pub skip)" if pub else "") + (f" ({sug} suggest skip)" if sug else ""))
    badge = ("BLOC pub/suggestions (skip plafonne, browse decidera la queue)" if res.get("filler_run")
             else "post COMPLET (meta visibles)" if full
             else "header cadre, meta sous le pli" if meta is False else "cadre")
    if res.get("on_reel"):
        return {"success": True, "message": f"scroll feed -> reel plein ecran ({mode})", "details": res}
    return {"success": True, "message": f"scroll feed [{mode}] {g} geste(s), {tail} — {badge}, {d} dumps",
            "details": res}


@action("scroll.feed_flick")
def scroll_feed_flick(a, p):
    """One strong FLICK only (A/B probe to measure the real fling coast on this device)."""
    h = a.scroll.screen_height
    ok = a.scroll._strong_flick("up", distance_px=0.33 * h)
    return {"success": bool(ok), "message": "flick fort (up)" if ok else "echec flick", "details": {}}


@action("scroll.feed_drag")
def scroll_feed_drag(a, p):
    """One long continuous DRAG only (A/B probe: 1:1 finger track, no coast)."""
    ok = a.scroll._long_drag("up")
    return {"success": bool(ok), "message": "drag continu (up)" if ok else "echec drag", "details": {}}


@action("reading.expand_caption")
def reading_expand_caption(a, p):
    """Open the truncated caption ('plus'/'more') of the dominant on-screen post, if any."""
    ok = a.scroll.expand_caption_if_truncated()
    return {"success": True,
            "message": "legende deroulee" if ok else "pas de legende tronquee a derouler",
            "details": {"expanded": bool(ok)}}


@action("reading.carousel_swipe")
def reading_carousel_swipe(a, p):
    """Swipe through 1-2 slides of the dominant on-screen carousel post, if any."""
    n = a.scroll.browse_carousel_slides()
    return {"success": True,
            "message": (f"carousel: {n} slide(s) parcourue(s)" if n else "pas de carousel a parcourir"),
            "details": {"slides": n}}


@action("scroll.read_pause")
def scroll_read_pause(a, p):
    """A human reading pause between scroll bursts (sampled from real inter-scroll gaps,
    median ~6s, long tail to ~25s+). Used to build a natural browse rhythm."""
    secs = a.scroll.human_reading_pause()
    return {"success": True, "message": f"lecture {secs:.1f}s", "details": {"seconds": round(secs, 1)}}


@action("scroll.browse")
def scroll_browse(a, p):
    """Human feed browsing: for `steps` READ posts, advance (stop smoothly on the engagement bar)
    + reading pause (carousel/caption). Skips Sponsored ads + Suggested units, occasionally skims
    past 1-2 posts."""
    steps = int(p.get("steps", 4))
    skip_ads = str(p.get("skip_ads", "1")).lower() not in ("0", "false", "no")
    skip_sugg = str(p.get("skip_suggested", "1")).lower() not in ("0", "false", "no")
    res = a.scroll.browse_feed(steps=steps, skip_ads=skip_ads, skip_suggested=skip_sugg)
    pauses = res.get("pauses_s") or []
    extra = []
    if res.get("ads_skipped"):
        extra.append(f"{res['ads_skipped']} pub(s) skip")
    if res.get("suggested_skipped"):
        extra.append(f"{res['suggested_skipped']} suggestion(s) skip")
    if res.get("skipped_posts"):
        extra.append(f"{res['skipped_posts']} post(s) saute(s)")
    suffix = (" — " + ", ".join(extra)) if extra else ""
    return {"success": not res.get("off_feed"),
            "message": (f"browse {res.get('steps')} posts lus, lectures {pauses}s{suffix}"
                        + (" — feed suivi epuise (stop)" if res.get("reached_tail") else "")
                        + (" — sorti du feed" if res.get("off_feed") else "")),
            "details": res}


@action("scroll.human_up")
def scroll_human_up(a, p):
    """One human-like swipe forward (feed up) — sampled real trajectory, no fixed coords."""
    ok = a.scroll._human_swipe("up")
    return {"success": bool(ok), "message": "swipe humain (up)" if ok else "echec swipe", "details": {}}


@action("scroll.human_down")
def scroll_human_down(a, p):
    """One human-like swipe backward (feed down) — sampled real trajectory."""
    ok = a.scroll._human_swipe("down")
    return {"success": bool(ok), "message": "swipe humain (down)" if ok else "echec swipe", "details": {}}


@action("scroll.left")
def scroll_left(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_left(scale=scale)
    return True


@action("scroll.right")
def scroll_right(a, p):
    scale = float(p.get("scale", 0.8))
    a.device.swipe_right(scale=scale)
    return True

