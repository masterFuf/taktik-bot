"""Android's permission prompt, met by the check of pages: granted when the bot works with it.

Decision of 2026-11-16: the check of pages grants the permission instead of refusing it. Before,
its close looked for a "permission_allow_button" or the words "Autoriser"/"Allow": on Android 12
and later the prompt has neither (its buttons are « Lorsque vous utilisez l'appli », « Uniquement
cette fois-ci », « Ne pas autoriser »), so the close fell to Back, which refuses the permission.

What is granted, and how:
- camera and microphone: « Uniquement cette fois-ci », the answer the publishing workflow already
  gives to the same prompts (`allow_prompts_this_time_only`), never a lasting grant;
- a permission the bot has no use for (contacts, location...) or a question it cannot read is not
  granted: Back refuses it, and the log says so.

The prompt is proven by the system's own ids, never by the words « Autoriser »/« Allow », which
Instagram's own screens carry too (its contacts request among them).

Screens: real dumps, anonymized. Android 12 in French over Instagram 410 (camera, microphone; the
camera one also under Instagram in English, the prompt speaking the phone's language), and the
older package installer in French asking for the contacts (« AUTORISER »/« REFUSER »).
"""

import pytest
from loguru import logger

from taktik.core.shared.device import permissions
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import PROBLEMATIC_PAGE_SELECTORS, locales
from unit.paths import CORE
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (
    SheetPhone, bounds_of, capture, node_with_id)

SHARED_FIXTURES = CORE / "tests/unit/shared/device/fixtures"
CAMERA = (SHARED_FIXTURES / "android12_fr_permission_camera.xml").read_text(encoding="utf-8")
MICROPHONE = (SHARED_FIXTURES / "android12_fr_permission_microphone.xml").read_text(encoding="utf-8")
CAMERA_OVER_ENGLISH_INSTAGRAM = capture("ig410_en_video_editor_camera_prompt_fr_system.xml")
CONTACTS_INSTALLER = capture("android_installer_fr_permission_contacts.xml")
INSTAGRAM_CONTACTS_REQUEST = capture("ig447_fr_discover_people_contacts_prompt.xml")
INSTAGRAM_BEHIND = capture("ig410_en_reel_editor.xml")

GRANTED = [
    pytest.param(CAMERA, "fr", id="camera, Android 12, French"),
    pytest.param(MICROPHONE, "fr", id="microphone, Android 12, French"),
    pytest.param(CAMERA_OVER_ENGLISH_INSTAGRAM, "en", id="camera, prompt in French, Instagram in English"),
]


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(permissions.time, "sleep", lambda *_a, **_k: None)
    run_halt.reinitialiser()
    before = locales.active_locale()
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


@pytest.fixture
def journal():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="DEBUG")
    yield lines
    logger.remove(sink)


def _inside(point, bounds):
    left, top, right, bottom = bounds
    return left <= point[0] <= right and top <= point[1] <= bottom


def _deny_buttons(xml):
    return [bounds_of(node_with_id(xml, suffix)) for suffix in
            ("permission_deny_button", "permission_deny_and_dont_ask_again_button")
            if f":id/{suffix}\"" in xml]


@pytest.mark.parametrize("prompt, language", GRANTED)
def test_camera_and_microphone_are_granted_only_this_time(prompt, language, journal):
    locales.set_active_locale(language)
    phone = SheetPhone(prompt, after=INSTAGRAM_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False,
                      "page_type": "android_permission_dialog"}
    assert len(phone.gestures) == 1, phone.gestures
    kind, x, y = phone.gestures[0]
    assert kind == "click", phone.gestures
    assert _inside((x, y), bounds_of(node_with_id(prompt, "permission_allow_one_time_button")))
    assert _deny_buttons(prompt)
    assert not any(_inside((x, y), deny) for deny in _deny_buttons(prompt))
    assert any(line.startswith("Android permission granted") for line in journal), journal


def test_contacts_are_never_granted_back_refuses_them_and_says_so(journal):
    locales.set_active_locale("fr")
    phone = SheetPhone(CONTACTS_INSTALLER, after=INSTAGRAM_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result["page_type"] == "android_permission_dialog"
    assert phone.gestures == [("press", "back")]
    refused = [line for line in journal if "refused by Back" in line]
    assert refused and "contacts" in refused[0], journal


def test_the_prompt_is_proven_by_system_ids_never_by_the_word_allow():
    """Instagram's contacts request says « Autoriser »: one word, once on screen, used to count as
    two indicators of the Android prompt (« Autoriser » and « AUTORISER », compared lowercased)."""
    detector = ProblematicPageDetector(SheetPhone(INSTAGRAM_CONTACTS_REQUEST, after=INSTAGRAM_BEHIND))
    pattern = PROBLEMATIC_PAGE_SELECTORS.detection_patterns["android_permission_dialog"]

    assert "Autoriser" in INSTAGRAM_CONTACTS_REQUEST
    assert not detector._matches(INSTAGRAM_CONTACTS_REQUEST, pattern)
    for prompt in (CAMERA, MICROPHONE, CAMERA_OVER_ENGLISH_INSTAGRAM, CONTACTS_INSTALLER):
        assert detector._matches(prompt, pattern)
