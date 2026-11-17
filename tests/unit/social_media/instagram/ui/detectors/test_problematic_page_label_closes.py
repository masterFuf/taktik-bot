"""The closes of the check of pages that tap a button by its label tap that page's own button.

A close runs once its page is detected, but it looks for its button on the whole screen: a field
that answers on other screens taps the wrong button as soon as a pattern detects a page by mistake.
Measured on 2 500 real captures (2026-11-17), the `x_button` close of the QR page answered on 602 of
them: the back arrow of a screen, the « Cancel » of the reel and post editors (the publication
dropped), the cross that removes a suggested account from a list. Its one true positive is the QR
page's own close button, found by its id on both captures of that page.

Screens: real dumps, anonymized. The QR page of the own profile (410 in English, 447 in French),
and screens where the old field tapped something else (410).
"""

import pytest

from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (
    SheetPhone, capture, centre_of, node_with_id)

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
