"""The closes of the check of pages that tap a button by its label tap that page's own button.

A close runs once its page is detected, but it looks for its button on the whole screen: a field
that answers on other screens taps the wrong button as soon as a pattern detects a page by mistake.
Measured on 2 500 real captures (2026-11-17), the `x_button` close of the QR page answered on 602 of
them: the back arrow of a screen, the « Cancel » of the reel and post editors (the publication
dropped), the cross that removes a suggested account from a list. Its one true positive is the QR
page's own close button, found by its id on both captures of that page.

The « OK » of Meta's ad-experience page was looked for by its text or its label anywhere: on 41 to 44
captures that is the OK that validates a caption, the Enter key of Google's keyboard, the OK of
another screen's information window. On the page itself, it is a Button without an id labelled
« OK »: no other capture has one.

The opposite also happened: the « Not now » of Instagram's map card was never found, and Back was
the only close left.

Screens: real dumps, anonymized. The QR page of the own profile (410 in English, 447 in French),
Meta's ad-experience page and Instagram's map card (English, April 2026, version not recorded),
and screens where the old fields tapped something else (410, 447).
"""

import re

import pytest

from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import POPUP_SELECTORS, PROBLEMATIC_PAGE_SELECTORS, locales
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (
    SheetPhone, attribute, capture, centre_of, node_with_id)

QR_PAGES = [
    pytest.param("ig410_en_qr_page.xml", id="qr page, 410, English"),
    pytest.param("ig447_fr_qr_page.xml", id="qr page, 447, French"),
]

# What the old field tapped on each of them.
NOT_THE_QR_PAGE = [
    pytest.param("ig410_fr_discover_people.xml", id="discover people: back arrow"),
    pytest.param("ig410_en_reel_editor.xml", id="reel editor: Cancel"),
    pytest.param("ig410_en_new_post_gallery_video_selected.xml", id="new post: Cancel"),
    pytest.param("ig410_fr_feed_suggestions_carousel.xml", id="feed suggestions: Fermer"),
    pytest.param("ig410_en_account_switcher.xml", id="account switcher: Cancel"),
    pytest.param("ig410_en_likers_sheet_two_likers_c57s.xml", id="likers sheet: Dismiss"),
]


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)


@pytest.mark.parametrize("name", QR_PAGES)
def test_the_x_close_taps_the_qr_page_close_button(name):
    screen = capture(name)
    phone = SheetPhone(screen, after=screen)

    assert ProblematicPageDetector(phone)._close_via_x() is True
    assert phone.gestures == [("click", *centre_of(node_with_id(screen, ":id/close_button")))]


@pytest.mark.parametrize("name", NOT_THE_QR_PAGE)
def test_the_x_close_taps_nothing_off_the_qr_page(name):
    screen = capture(name)
    phone = SheetPhone(screen, after=screen)

    assert ProblematicPageDetector(phone)._close_via_x() is False
    assert phone.gestures == []


@pytest.mark.parametrize("name", QR_PAGES)
def test_a_qr_page_back_leaves_open_is_closed_by_its_close_button(name):
    screen = capture(name)
    phone = SheetPhone(screen, after=[screen, capture("ig410_fr_own_profile.xml")])

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False, "page_type": "qr_code_page"}
    assert phone.gestures == [("press", "back"),
                              ("click", *centre_of(node_with_id(screen, ":id/close_button")))]


AD_EXPERIENCE = "ig_en_ad_experience_page.xml"

# Their « OK » is another screen's: what the old fields tapped there.
OTHER_OKS = [
    pytest.param("ig410_en_new_reel_caption_typed.xml", id="caption: its OK validates the caption"),
    pytest.param("ig447_fr_dm_new_message_results_named_account.xml", id="Google keyboard: its Enter key"),
    pytest.param("ig410_en_story_share_information_window.xml", id="information window: its OK"),
]


def _ad_experience_ok(xml):
    """The page's « OK »: a Button labelled OK, without an id."""
    found = [tag for tag in re.findall(r"<node\b[^>]*>", xml)
             if attribute(tag, "class") == "android.widget.Button" and attribute(tag, "content-desc") == "OK"
             and not attribute(tag, "resource-id")]
    assert len(found) == 1, found
    return found[0]


def test_the_ad_experience_page_is_closed_by_its_own_ok():
    screen = capture(AD_EXPERIENCE)
    phone = SheetPhone(screen, after=capture("ig410_fr_home_feed.xml"))

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False, "page_type": "meta_ad_experience"}
    assert phone.gestures == [("click", *centre_of(_ad_experience_ok(screen)))]


@pytest.mark.parametrize("name", OTHER_OKS)
def test_the_ad_experience_close_taps_no_other_ok(name):
    screen = capture(name)
    phone = SheetPhone(screen, after=screen)
    close_methods = PROBLEMATIC_PAGE_SELECTORS.detection_patterns["meta_ad_experience"]["close_methods"]

    ProblematicPageDetector(phone)._close_problematic_page("meta_ad_experience", close_methods)

    assert [gesture for gesture in phone.gestures if gesture[0] == "click"] == []


@pytest.mark.parametrize("name", OTHER_OKS)
def test_the_ad_consent_ok_answers_on_no_other_screen(name):
    """The same « OK » closes the third page of the ad consent flow, in the check of pages and at
    login: one selector for one button."""
    phone = SheetPhone(capture(name), after=capture(name))

    assert not any(phone.xpath(selector).exists for selector in POPUP_SELECTORS.ad_consent_ok_button)


MAP_POPUP = "ig_en_instagram_map_popup.xml"


@pytest.fixture
def english():
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)


def test_the_map_card_is_closed_by_its_not_now(english):
    """Its « Not now » is the card's secondary action, labelled on a FrameLayout (« now » in lower
    case): the close looked for « Not Now » on a Button or a TextView, found nothing, and Back was
    the only gesture left."""
    screen = capture(MAP_POPUP)
    phone = SheetPhone(screen, after=capture("ig410_fr_home_feed.xml"))

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False, "page_type": "instagram_map_popup"}
    assert phone.gestures == [
        ("click", *centre_of(node_with_id(screen, ":id/igds_headline_secondary_action_text_button")))]


@pytest.mark.parametrize("name", [
    pytest.param("ig410_en_story_share_information_window.xml", id="information window: View settings"),
    pytest.param("ig410_en_feed_carousel_cut_by_tab_bar.xml", id="feed card: its own Not now"),
])
def test_the_not_now_close_taps_no_other_secondary_action(name, english):
    screen = capture(name)
    phone = SheetPhone(screen, after=screen)

    ProblematicPageDetector(phone)._close_via_not_now()

    assert phone.gestures == []
