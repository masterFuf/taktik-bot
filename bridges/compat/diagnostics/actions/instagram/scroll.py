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
    """ONE decisive human gesture to reveal the next post (flick / continuous drag),
    real OS fling coast — not a burst of mini-scrolls. One dump measures the landing; one nudge
    if the post lands low. Surface-safe (never taps a reel/link/story); recovers if off-feed."""
    skip_ads = str(p.get("skip_ads", "1")).lower() not in ("0", "false", "no")
    skip_sugg = str(p.get("skip_suggested", "1")).lower() not in ("0", "false", "no")
    res = a.scroll.scroll_feed_to_next_post(skip_ads=skip_ads, skip_suggested=skip_sugg)
    snapshot = getattr(a.scroll, "_behavior_snapshot", lambda: {})()
    if snapshot:
        res["behavior_state"] = snapshot
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
    decision = res.get("advance_decision") or {}
    style = decision.get("style")
    energy = decision.get("energy")
    style_suffix = f", style={style}" if style else ""
    if energy is not None:
        style_suffix += f", energy={energy}"
    return {"success": True, "message": f"scroll feed [{mode}] {g} geste(s){style_suffix}, {tail} — {badge}, {d} dumps",
            "details": res}


@action("scroll.reveal_post")
def scroll_reveal_post(a, p):
    """Bring a real post's ENGAGEMENT BAR (like/comment row) into view so post.* tests
    can actually run. Uses the intelligent feed scroll: reveal the current post's
    metadata, else advance to the next real post (skips ads/suggested), framed with its
    bar visible. Success = the bar is genuinely visible (a precondition for post.is_liked,
    post.like, post.open_comments…); a failure lets those tests be flagged "blocked"
    instead of a false broken-selector red."""
    fs = a.scroll
    fs._reveal_current_metadata()
    anchors = fs._read_feed_anchors()
    if anchors.get("on_feed") and fs._metadata_visible(anchors)[0] and not fs._dominant_is_ad(anchors):
        return {"success": True, "message": "barre d'engagement du post visible (post courant)",
                "details": {"advanced": False}}
    res = fs.scroll_feed_to_next_post(skip_ads=True, skip_suggested=True)
    ok = bool(res.get("metadata_visible") or res.get("full_post"))
    return {"success": ok,
            "message": ("barre d'engagement du post visible" if ok else "barre d'engagement non atteinte (pub/suggestion ?)"),
            "details": res}


@action("scroll.feed_flick")
def scroll_feed_flick(a, p):
    """One strong FLICK only (A/B probe to measure the real fling coast on this device)."""
    h = a.scroll.screen_height
    ok = a.scroll._strong_flick("up", distance_px=0.33 * h, guard_start=True)
    return {"success": bool(ok), "message": "flick fort (up)" if ok else "echec flick", "details": {}}


@action("scroll.feed_drag")
def scroll_feed_drag(a, p):
    """Regression probe for the post Share long-press.

    Requests the production drag from the live Share bounds. The production start-zone guard must
    move the actual touch-down to a neutral gap, and the low-level touch path must not open the
    Direct share sheet. Run with a post action row visible (``scroll.reveal_post`` can prepare it).
    """
    modal_before = a.popup._detect_blocking_modal()
    if modal_before:
        return {
            "success": False,
            "message": f"precondition bloquee par la modale {modal_before}",
            "details": {"blocked": "modal_already_open", "modal": modal_before},
        }

    share_bounds = a.scroll._post_action_bounds("share")
    if not share_bounds:
        return {
            "success": False,
            "message": "bouton share non visible (afficher d'abord la barre d'engagement)",
            "details": {"blocked": "share_not_visible"},
        }

    h = int(a.scroll.screen_height)
    target = min(
        share_bounds,
        key=lambda box: abs(((box[1] + box[3]) / 2.0) - (0.815 * h)),
    )
    requested = ((target[0] + target[2]) // 2, (target[1] + target[3]) // 2)
    ok = a.scroll._long_drag("up", start_point=requested, guard_start=True)
    start = dict(getattr(a.scroll, "_last_gesture_start", {}))
    modal_after = a.popup._detect_blocking_modal()
    safe = bool(start.get("adjusted")) and modal_after is None
    return {
        "success": bool(ok and safe),
        "message": (
            "drag post protege: depart share deplace, aucune modale"
            if ok and safe
            else f"echec garde drag (modal={modal_after}, adjusted={start.get('adjusted')})"
        ),
        "details": {
            "share_bounds": target,
            "requested_start": requested,
            "gesture_start": start,
            "modal_after": modal_after,
        },
    }


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
    decision = dict(getattr(a.scroll, "_last_carousel_behavior", {}))
    snapshot = getattr(a.scroll, "_behavior_snapshot", lambda: {})()
    return {"success": True,
            "message": (f"carousel: {n} slide(s) parcourue(s)" if n else "pas de carousel a parcourir"),
            "details": {"slides": n, "gesture_decision": decision,
                        "behavior_state": snapshot}}


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
    past 1-2 posts. Toggles (Lab scenario controls): skip_ads, skip_suggested, read_captions,
    browse_carousels; `steps` (1-30) sets how many posts to read."""
    def _flag(key, default="1"):
        return str(p.get(key, default)).lower() not in ("0", "false", "no")
    steps = max(1, min(30, int(p.get("steps", 6))))
    skip_ads = _flag("skip_ads")
    skip_sugg = _flag("skip_suggested")
    read_captions = _flag("read_captions")
    browse_carousels = _flag("browse_carousels")
    res = a.scroll.browse_feed(steps=steps, skip_ads=skip_ads, skip_suggested=skip_sugg,
                               read_captions=read_captions, browse_carousels=browse_carousels)
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
