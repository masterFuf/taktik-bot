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
    """Select the first gallery media thumbnail (image or video)."""
    ok = a.click._find_and_click('(//*[contains(@resource-id, "gallery_grid_item_thumbnail")])[1]', timeout=4)
    return _result(ok, "1er media selectionne", "gallery item introuvable", selector="gallery_grid_item_thumbnail")


@action("publish.enable_multi_select")
def publish_enable_multi_select(a, p):
    """Enable carousel multi-select."""
    selectors = [_rid(CC.multi_select_slide_button_alt)] + _by_texts([
        "Select multiple button", "Bouton de sélection multiple",
    ])
    ok = a.click._find_and_click(selectors, timeout=4)
    return _result(ok, "multi-select active", "multi-select introuvable", selector="multi_select_slide_button_alt")


@action("publish.select_reel_tab")
def publish_select_reel_tab(a, p):
    """Select the REEL tab in the gallery."""
    ok = a.click._find_and_click(_by_texts(CC.reel_type_texts), timeout=4)
    return _result(ok, "onglet REEL selectionne", "onglet REEL introuvable", selector="reel_type_texts")


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
    ok = a.kb.type_text(text)
    return {"success": bool(ok), "message": f"caption: {text[:40]}" if ok else "echec saisie caption",
            "details": {"text": text}}


@action("publish.dismiss_keyboard")
def publish_dismiss_keyboard(a, p):
    """Close the soft keyboard (press back) so the footer Share button becomes reachable.

    After typing the caption the IME covers the Share button (it sits in the footer);
    a single back press closes the keyboard without leaving the composer."""
    try:
        a.device.back()
        ok = True
    except Exception:
        ok = False
    return {"success": True, "message": "clavier ferme" if ok else "echec fermeture clavier",
            "details": {"dismissed": ok}}


@action("publish.tap_share")
def publish_tap_share(a, p):
    """Tap the final Share button."""
    selectors = [_rid(CC.share_footer_button), _rid(CC.share_button)] + _by_texts(CC.publish_texts)
    ok = a.click._find_and_click(selectors, timeout=4)
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
