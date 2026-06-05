"""Instagram publish (content creation) actions for compat diagnostics.

Selector-only (NO hardcoded coordinates): each step finds its element by resource-id or
text and reports whether the selector matched, so the Cartography Lab can validate the
publish flow step by step before assembling the bot publish bridge.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action
from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS as CC,
)


def _rid(resource_id: str) -> str:
    """XPath matching a resource-id (suffix-tolerant)."""
    return f'//*[contains(@resource-id, "{resource_id.split("/")[-1]}")]'


def _by_texts(texts) -> list:
    """XPath list matching any of the given text/content-desc labels."""
    selectors = []
    for t in texts:
        selectors.append(f'//*[@text="{t}"]')
        selectors.append(f'//*[@content-desc="{t}"]')
    return selectors


def _result(found: bool, ok_msg: str, ko_msg: str, **details):
    return {
        "success": bool(found),
        "message": ok_msg if found else ko_msg,
        "details": {"found": bool(found), **details},
    }


@action("publish.dismiss_reel_draft")
def publish_dismiss_reel_draft(a, p):
    """Dismiss the 'keep editing your draft?' modal if present (optional)."""
    selectors = [_rid(CC.auxiliary_button)] + _by_texts(CC.reel_draft_start_new_texts)
    ok = a.click._find_and_click(selectors, timeout=2)
    # Non-blocking: the modal is conditional.
    return {"success": True, "message": "draft modal ferme" if ok else "pas de draft modal",
            "details": {"dismissed": ok}}


@action("publish.open_creation")
def publish_open_creation(a, p):
    """Open the creation screen. Selector-only: bottom-bar create tab, else the clickable
    ImageView in the top-left action bar container (no resource-id/content-desc on some
    versions), else a 'Create' label. No hardcoded coordinate."""
    selectors = list(CC.create_button_xpaths) + _by_texts(CC.create_button_texts)
    ok = a.click._find_and_click(selectors, timeout=4)
    return _result(ok, "creation ouverte", "bouton creer introuvable", selector="create_button")


@action("publish.select_first_gallery")
def publish_select_first_gallery(a, p):
    """Select the first gallery media thumbnail (image or video). If the create flow
    landed on the camera (no grid), open the gallery first via the preview button."""
    if not a.click._is_element_present(CC.gallery_grid_xpaths()):
        a.click._find_and_click(CC.gallery_open_xpaths(), timeout=3)
        a.click._wait_for_element(CC.gallery_grid_xpaths(), timeout=5, silent=True)
    ok = a.click._find_and_click(CC.first_gallery_item_xpath(), timeout=5)
    return _result(ok, "1er media selectionne", "gallery item introuvable", selector="gallery_grid_item_thumbnail")


@action("publish.enable_multi_select")
def publish_enable_multi_select(a, p):
    """Enable carousel multi-select."""
    ok = a.click._find_and_click(CC.multi_select_xpaths(), timeout=4)
    return _result(ok, "multi-select active", "multi-select introuvable", selector="multi_select_slide_button_alt")


@action("publish.clear_gallery_selection")
def publish_clear_gallery_selection(a, p):
    """Deselect every currently-selected thumbnail (clean slate before a carousel).

    Enabling multi-select auto-selects the previewed thumbnail, which is NOT always grid
    #1 (a stale preview can be selected at any position). Clearing first lets the carousel
    select grid[1..N] deterministically. Idempotent: a no-op when nothing is selected."""
    cleared = 0
    for _ in range(12):
        if _selected_media_count(a) == 0:
            break
        if not a.click._find_and_click(CC.selected_media_xpath(), timeout=2):
            break
        cleared += 1
    total = _selected_media_count(a)
    return {"success": True, "message": f"selection purgee ({cleared} deselectionne(s), {total} restant(s))",
            "details": {"cleared": cleared, "selected_total": total}}


def _selected_media_count(a) -> int:
    """Count gallery thumbnails currently selected (content-desc based)."""
    try:
        return len(a.device.xpath(CC.selected_media_xpath()).all())
    except Exception:
        return 0


def _is_gallery_item_selected(a, idx: int) -> bool:
    """Whether the Nth thumbnail is already selected (avoids deselect-on-retap)."""
    try:
        return a.click._is_element_present(CC.gallery_item_selected_xpath(idx))
    except Exception:
        return False


@action("publish.select_gallery_item")
def publish_select_gallery_item(a, p):
    """Select the Nth gallery thumbnail (param 'index', 1-based). For carousel.

    Idempotent: entering multi-select auto-selects thumbnail #1, and re-tapping a
    selected thumbnail DESELECTS it (which would silently turn a carousel into a single
    post). So we skip the tap when the item is already selected, and report the live
    selected count so the Lab scenario reflects the real carousel state."""
    idx = int(p.get("index", 1))
    if _is_gallery_item_selected(a, idx):
        total = _selected_media_count(a)
        return _result(True, f"media {idx} deja selectionne ({total} au total)",
                       "", index=idx, already_selected=True, selected_total=total)
    ok = a.click._find_and_click(CC.gallery_item_xpath(idx), timeout=4)
    total = _selected_media_count(a)
    return _result(ok, f"media {idx} selectionne ({total} au total)",
                   f"media {idx} introuvable", index=idx, selected_total=total)


@action("publish.select_story_tab")
def publish_select_story_tab(a, p):
    """Select the STORY mode/tab in the create surface (best-effort)."""
    ok = a.click._find_and_click(CC.story_mode_xpaths(), timeout=3)
    return {"success": True, "message": "onglet STORY selectionne" if ok else "pas d'onglet STORY",
            "details": {"selected": ok}}


@action("publish.select_post_tab")
def publish_select_post_tab(a, p):
    """Select the POST destination tab (feed post / carousel). Required for multi-select."""
    ok = a.click._find_and_click(CC.post_tab_xpaths(), timeout=4)
    return _result(ok, "onglet POST selectionne", "onglet POST introuvable", selector="cam_dest_feed")


@action("publish.select_reel_tab")
def publish_select_reel_tab(a, p):
    """Select the REEL destination tab."""
    ok = a.click._find_and_click(CC.reel_tab_xpaths(), timeout=4)
    return _result(ok, "onglet REEL selectionne", "onglet REEL introuvable", selector="cam_dest_clips")


@action("publish.next")
def publish_next(a, p):
    """Tap the Next button (gallery -> filters, or filters -> caption)."""
    selectors = [_rid(CC.creation_next_button), _rid(CC.next_button)] + _by_texts(CC.next_texts)
    ok = a.click._find_and_click(selectors, timeout=4)
    return _result(ok, "Next clique", "Next introuvable")


@action("publish.dismiss_modal_ok")
def publish_dismiss_modal_ok(a, p):
    """Dismiss an optional post-selection modal (OK), if present."""
    selectors = [_rid(CC.bb_primary_action_container)] + _by_texts(["OK"])
    ok = a.click._find_and_click(selectors, timeout=2)
    return {"success": True, "message": "modal OK ferme" if ok else "pas de modal", "details": {"dismissed": ok}}


@action("publish.tap_caption")
def publish_tap_caption(a, p):
    """Tap the caption field to focus it."""
    selectors = [_rid(CC.caption_input_text_view), _rid(CC.caption_text_view)]
    ok = a.click._find_and_click(selectors, timeout=4)
    return _result(ok, "champ caption ouvert", "caption introuvable", selector="caption_input_text_view")


@action("publish.type_caption")
def publish_type_caption(a, p):
    """Type a caption (param 'text'). The caption field must be focused first."""
    text = p.get("text", "Test caption Lab")
    # clear_first: the composer may restore a previous draft caption -> avoid duplicates.
    ok = a.kb.type_text(text, clear_first=True)
    return {"success": bool(ok), "message": f"caption: {text[:40]}" if ok else "echec saisie caption",
            "details": {"text": text}}


@action("publish.confirm_caption")
def publish_confirm_caption(a, p):
    """Confirm the full-screen caption editor (tap OK/Done) to return to the composer.

    Tapping the caption opens a dedicated editor (header 'New reel'/'New post' + OK
    top-right) with the custom auto-typing IME. Pressing back does NOT close it; the
    OK button commits the caption and returns to the composer where Share lives."""
    ok = a.click._find_and_click(CC.caption_confirm_xpaths(), timeout=4)
    return _result(ok, "caption validee (OK)", "bouton OK introuvable", selector="caption_done_button")


@action("publish.dismiss_keyboard")
def publish_dismiss_keyboard(a, p):
    """Close the soft keyboard (press back). Fallback only — for the caption editor use
    publish.confirm_caption (OK) which both commits the caption and returns to the composer."""
    try:
        a.device.back()
        ok = True
    except Exception:
        ok = False
    return {"success": True, "message": "clavier ferme" if ok else "echec fermeture clavier",
            "details": {"dismissed": ok}}


@action("publish.tap_share")
def publish_tap_share(a, p):
    """Tap the final Share button. Uses the shared provider so text/content-desc 'Share'
    is tried first (targets the real button, not the full-width share_button_container
    whose center misses it)."""
    ok = a.click._find_and_click(CC.share_button_xpaths(), timeout=4)
    return _result(ok, "Share clique", "Share introuvable")


@action("publish.open_story_gallery")
def publish_open_story_gallery(a, p):
    """Story flow: open the gallery from the story camera."""
    selectors = [_rid(CC.gallery_preview_button)] + _by_texts(["Gallery", "Galerie"])
    ok = a.click._find_and_click(selectors, timeout=4)
    return _result(ok, "galerie story ouverte", "bouton galerie introuvable", selector="gallery_preview_button")


@action("publish.tap_your_story")
def publish_tap_your_story(a, p):
    """Story flow: tap the 'Your story' publish button."""
    ok = a.click._find_and_click(_by_texts(["Your story", "Votre story"]), timeout=4)
    return _result(ok, "Your story clique", "Your story introuvable", selector="your_story")


@action("publish.dismiss_story_promo")
def publish_dismiss_story_promo(a, p):
    """Dismiss the one-time 'Introducing story-to-story sharing' promo shown after a
    story is published (igds headline -> OK). Non-blocking: it only appears the first time."""
    ok = a.click._find_and_click(CC.story_share_promo_dismiss_xpaths(), timeout=4)
    return {"success": True, "message": "promo story-to-story fermee" if ok else "pas de promo story",
            "details": {"dismissed": ok}}


@action("publish.open_story_from_feed")
def publish_open_story_from_feed(a, p):
    """2nd story-entry method: tap our own bubble in the feed reels tray ("Add to story")
    to open story creation directly from the feed (no create "+" / STORY tab)."""
    ok = a.click._find_and_click(CC.feed_story_tray_add_xpaths(), timeout=5)
    return _result(ok, "story ouverte depuis le feed", "bubble 'Add to story' introuvable",
                   selector="reel_empty_badge")
