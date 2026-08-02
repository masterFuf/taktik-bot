"""Scroll actions for Instagram compat diagnostics."""

import time

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.shared.behavior.gesture import sample_swipe
from taktik.core.shared.behavior.gesture_primitives import _step_cost as _gesture_step_cost


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


@action("scroll.hashtag_next_post")
def scroll_hashtag_next_post(a, p):
    """Post viewer (hashtag) -> advance to the next post AND prove it changed.

    The exact production function used by the hashtag workflow — not a Lab-only path. It
    reads the post identity (likes/comments/reel), advances, re-reads, and retries with a
    longer travel while the post has not changed. The gesture follows the surface: a REEL is
    a pager and gets a real fling (below its velocity threshold it springs back to the same
    reel — that is what "it takes several tries to change reel" was), a post detail is a list
    and keeps the controlled curve so the extractor never reads the wrong post. Run it on a
    reel: that is where the workflow used to loop on one post until its budget ran out."""
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import HashtagBusiness

    hashtag = HashtagBusiness(a.device)
    is_reel = hashtag._is_reel_post()
    ratios = HashtagBusiness._NEXT_REEL_RATIOS if is_reel else HashtagBusiness._NEXT_POST_RATIOS
    gesture = "flick" if is_reel else "scroll controle"

    before = hashtag._current_post_signature()
    moved = hashtag._swipe_to_next_post(known_signature=before)
    after = hashtag._current_post_signature()

    details = {
        "signature_before": before, "signature_after": after, "moved": moved,
        "is_reel": is_reel, "gesture": gesture, "ratios": list(ratios),
    }
    if moved:
        return {
            "success": True,
            "message": f"post suivant atteint en {gesture} ({before} -> {after})",
            "details": details,
        }
    return {
        "success": False,
        "message": f"toujours sur le meme post apres {len(ratios)} {gesture} "
                   f"(signature {before}) — fin de liste, ou visionneuse bloquee",
        "details": details,
    }


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


def _anchors_for(device, selectors, limit: int = 80):
    anchors = {}
    for selector in selectors:
        try:
            for node in device.xpath(selector).all()[:limit]:
                try:
                    key = (node.attrib.get("content-desc") or node.text or "").strip()
                    if len(key) < 4:
                        continue
                    _, top, _, bottom = node.bounds
                    anchors.setdefault(key, (top + bottom) // 2)
                except Exception:
                    continue
        except Exception:
            continue
    return anchors


def _screen_anchors(device):
    """Map SCROLLABLE-CONTENT items to their vertical centre, and say whether scoping worked.

    Two lessons are baked in here, both from device runs.

    Keys on text OR content-desc: a photo feed carries almost no TextView, so a text-only probe
    found one common anchor there and had to call itself inconclusive. Instagram labels its media
    ("Photo by ... on ..."), so content-desc is what makes the measurement possible on the surface
    that needs it most.

    But content-desc also drags in the STATIC chrome, and that produced a flatly wrong answer: on a
    feed that had genuinely scrolled 1297px, 11 of 21 matched anchors were the Android nav bar, the
    Instagram tab bar and the status bar, all at +0 — so the median landed on zero and the probe
    reported a motionless screen. Scoping to the scrollable container removes them structurally
    rather than by guessing at screen regions: chrome lives outside the RecyclerView by
    construction. Replayed on the two real dumps, it goes from 21 anchors / median 0px to
    10 anchors / median 1297px.
    """
    scoped = _anchors_for(device, ('//*[@scrollable="true"]//*[@content-desc]',
                                   '//*[@scrollable="true"]//android.widget.TextView'))
    if len(scoped) >= 3:
        return scoped, True
    # No scrollable container exposed (a dialog, a full-screen viewer): fall back to the whole
    # screen and flag it, because the reading is then chrome-contaminated and must be read as such.
    return _anchors_for(device, ('//*[@content-desc]', '//android.widget.TextView')), False


@action("scroll.controlled_step")
def scroll_controlled_step(a, p):
    """Measure what ONE production controlled scroll really moves on screen.

    Runs `device.human_scroll("down", distance_ratio=R)` — the shared entry point itself, no
    Lab-only path — and compares the position of the texts visible before and after, so it reports
    the displacement the CONTENT underwent, not the one we asked the finger for.

    What it settles: `coast=False` promises a 1:1 gesture with no overshoot. It used to take the
    fling branch, so the content travelled the finger distance PLUS an Android coast, and the
    callers that advance one post per scroll could sail past one. Displacement close to the request
    means the contract holds; a large excess means a fling is still happening.

    Run it in the view you care about — the hashtag flows use R=0.62 in the post viewer.
    """
    ratio = max(0.10, min(0.95, float(p.get("distance_ratio", 0.62))))
    h = int(a.scroll.screen_height)
    requested = int(ratio * h)

    before, scoped = _screen_anchors(a.device)
    a.device.human_scroll("down", distance_ratio=ratio)
    time.sleep(0.9)
    after, _ = _screen_anchors(a.device)

    common = [k for k in before if k in after]
    shifts = sorted(before[k] - after[k] for k in common)
    injection = dict(getattr(a.scroll, "_last_gesture_injection", None) or {})
    details = {"requested_px": requested, "distance_ratio": ratio, "screen_height": h,
               "anchors_before": len(before), "anchors_after": len(after),
               "anchors_matched": len(shifts), "scoped_to_scrollable": scoped,
               "shifts_px": shifts, "injection": injection}

    if len(shifts) < 3:
        return {"success": False,
                "message": (f"non concluant: {len(shifts)} ancre(s) commune(s) — le contenu a "
                            f"defile de plus d'un ecran, ou la vue n'offre rien de stable"),
                "details": details}

    moved = shifts[len(shifts) // 2]
    excess = (moved / requested) if requested else 0.0
    # A screen with nothing left to scroll cannot be told apart from a gesture that fell short --
    # not from one reading. Anchor survival looked like the discriminator and is not: measured on
    # two consecutive gestures in the post viewer it was 95% for a genuine 1149px move and 85% for a
    # 310px one. So only a near-motionless screen is called end-of-content; anything between that
    # and the requested travel is reported as UNDETERMINED, naming both causes rather than blaming
    # the gesture. A probe that cries failure on healthy behaviour is worse than one that abstains.
    stalled = abs(moved) < 0.05 * requested
    details.update(measured_px=moved, ratio_measured_over_requested=round(excess, 2),
                   end_of_content=stalled)

    if stalled:
        verdict, ok = ("ecran immobile — plus rien a faire defiler (fin de contenu), "
                       "le geste n'est pas en cause"), True
    elif excess > 1.25:
        verdict, ok = f"DEPASSEMENT x{excess:.2f} — un fling se produit encore", False
    elif excess < 0.6:
        verdict, ok = (f"INDETERMINE x{excess:.2f} — soit la fin du contenu approche, soit le geste "
                       f"n'a pas sa course; un seul releve ne permet pas de trancher"), False
    else:
        verdict, ok = f"controle x{excess:.2f}", True
    suffix = "" if scoped else " (hors conteneur scrollable: lecture polluee par le chrome fixe)"
    return {"success": ok,
            "message": (f"demande {requested}px ({ratio:.2f}h), mesure {moved}px sur "
                        f"{len(shifts)} ancres — {verdict}{suffix}"),
            "details": details}


@action("scroll.gesture_bench")
def scroll_gesture_bench(a, p):
    """A/B the two gesture pacings on THIS device, on numbers instead of on the eye.

    Runs the SAME production path twice — once handed whole to the device (`_execute_device_path`,
    one round trip, the device injects a move every 5 ms) and once paced from the PC
    (`_execute_touch_path`, one JSON-RPC round trip per point) — and reports events, round trips
    and the effective injection rate. Up then down, so the feed lands back where it started.

    Reference: a real finger reports at 60-120 Hz. Below ~30 Hz the content advances in visible
    teleports, which is what reads as lag through the mirror.
    """
    fs = a.scroll
    h, w = int(fs.screen_height), int(fs.screen_width)
    raw = getattr(fs.device, "_device", None)
    if raw is None:
        return {"success": False, "message": "device brut indisponible", "details": {}}

    ratio = max(0.2, min(0.75, float(p.get("distance_ratio", 0.55))))
    runs = []
    for mode, direction, band in (("device", "up", (0.60 * h, 0.70 * h)),
                                  ("rpc", "down", (0.30 * h, 0.38 * h))):
        path, duration = sample_swipe(w, h, direction=direction, distance_px=ratio * h,
                                      start_band=band, dist_cap_h=0.95)
        path = fs._prepare_gesture_path(path, guard_start=True)
        fs._last_gesture_injection = None
        started = time.perf_counter()
        if mode == "device":
            ok = fs._execute_device_path(raw, path, duration)
        else:
            touch = fs._touch_api(raw)
            ok = touch is not None
            if ok:
                fs._execute_touch_path(touch, path, duration)
        elapsed = time.perf_counter() - started
        info = dict(getattr(fs, "_last_gesture_injection", None) or {})
        events = int(info.get("events") or 0)
        runs.append({
            "mode": mode, "direction": direction, "ok": bool(ok),
            "asked_ms": round(duration * 1000), "measured_ms": round(elapsed * 1000),
            "events": events, "rpc_calls": info.get("rpc_calls"),
            "hz": round(events / elapsed, 1) if elapsed > 0 and events else None,
            "overshoot_pct": round((elapsed / duration - 1) * 100) if duration > 0 else None,
            "injection": info,
        })
        time.sleep(0.9)   # let the previous motion settle before measuring the next

    by_mode = {r["mode"]: r for r in runs}
    dev, rpc = by_mode.get("device", {}), by_mode.get("rpc", {})
    if not dev.get("ok"):
        return {"success": False, "message": "cadence device indisponible (swipePoints absent ?)",
                "details": {"runs": runs}}
    gain = (round(dev["hz"] / rpc["hz"], 1) if dev.get("hz") and rpc.get("hz") else None)
    # The per-step cost is what sizes every device-paced gesture, so show it: it is the number to
    # look at when a gesture runs long. Both values matter and they differ on the first run of a
    # session: `planifie` is what the path was sized with (the seed, until a gesture has been
    # measured), `mesure` is what this phone actually charged. Once they agree, the pacing is
    # calibrated -- and the bench, being the first device-paced gesture, is precisely where they
    # do not yet.
    planned_step = (dev.get("injection") or {}).get("step_cost_ms")
    learned_step = round(_gesture_step_cost(raw) * 1000, 1)
    summary = (f"device {dev['hz']}Hz en {dev['events']} events / 1 aller-retour "
               f"({dev['measured_ms']}ms pour {dev['asked_ms']}ms demandes"
               + (f", pas planifie {planned_step}ms -> mesure {learned_step}ms" if planned_step else "")
               + ")")
    if rpc.get("ok"):
        summary += (f" | PC {rpc['hz']}Hz en {rpc['events']} events / {rpc['rpc_calls']} "
                    f"allers-retours ({rpc['measured_ms']}ms, +{rpc['overshoot_pct']}%)")
        if gain:
            summary += f" -> x{gain}"
    return {"success": True, "message": summary, "details": {"runs": runs, "gain": gain}}


@action("reading.expand_caption")
def reading_expand_caption(a, p):
    """Open the truncated caption ('plus'/'more') of the dominant on-screen post, if any."""
    ok = a.scroll.expand_caption_if_truncated()
    return {"success": True,
            "message": "legende deroulee" if ok else "pas de legende tronquee a derouler",
            "details": {"expanded": bool(ok)}}


@action("reading.carousel_swipe")
def reading_carousel_swipe(a, p):
    """Swipe only when the current carousel is fully framed and unambiguous."""
    n = a.scroll.browse_carousel_slides()
    decision = dict(getattr(a.scroll, "_last_carousel_behavior", {}))
    skip_reason = getattr(a.scroll, "_last_carousel_skip_reason", None)
    snapshot = getattr(a.scroll, "_behavior_snapshot", lambda: {})()
    return {"success": True,
            "message": (f"carousel: {n} slide(s) parcourue(s)" if n
                        else f"carousel ignore ({skip_reason or 'absent'})"),
            "details": {"slides": n, "gesture_decision": decision,
                        "skip_reason": skip_reason,
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


def _generic_scroll(a, p, direction: str):
    """Run the production generic scroll and report which gesture profile it took."""
    try:
        distance_ratio = float(p.get("distance_ratio", 0.4))
    except (TypeError, ValueError):
        distance_ratio = 0.4
    speed = str(p.get("speed", "normal")).strip().lower()
    if speed not in ("normal", "slow"):
        speed = "normal"
    runner = a.scroll.scroll_up if direction == "up" else a.scroll.scroll_down
    ok = runner(distance_ratio=distance_ratio, speed=speed)
    decision = dict(getattr(a.scroll, "_last_behavior_gesture", {}) or {})
    profile = "curve echantillonnee" if speed == "slow" else "flick decisif"
    style = f" style={decision.get('style')}" if decision.get("style") else ""
    return {
        "success": bool(ok),
        "message": f"scroll {direction} [{profile}] ratio={distance_ratio}{style}",
        "details": {
            "direction": direction,
            "distance_ratio": distance_ratio,
            "speed": speed,
            "gesture_decision": decision,
            "behavior_state": getattr(a.scroll, "_behavior_snapshot", lambda: {})(),
        },
    }


@action("scroll.generic_up")
def scroll_generic_up(a, p):
    """The production generic scroll (``ScrollActions.scroll_up``) — the entry point the
    workflows call, not one of the primitives underneath it.

    Covers the whole composition in one run: direction routing, ``distance_ratio`` resolved
    against the real screen height, the decisive flick (``speed='normal'``) or the sampled
    curve (``speed='slow'``), then the human settle delay. ``scroll.human_up`` and
    ``scroll.feed_flick`` each exercise ONE primitive underneath; this exercises what
    production actually invokes, so a routing regression cannot hide between them.

    params (optional):
      - distance_ratio: fraction of the screen height (production default 0.4).
      - speed: 'normal' (decisive flick, default) or 'slow' (sampled curve).
    """
    return _generic_scroll(a, p, "up")


@action("scroll.generic_down")
def scroll_generic_down(a, p):
    """Same production entry point, backward (``ScrollActions.scroll_down``). Same params."""
    return _generic_scroll(a, p, "down")


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
