"""A profile is never a problematic page; the pages themselves still are.

Opening the connected account's own profile, the detector found the label of the profile's
own share button, called the screen `qr_code_page` (one word of three was its threshold) and
pressed Back: the profile was left before its counters were read. With that pattern narrowed,
the same profile fell to `profile_share_page` (its avatar's story badge, its share button and
its Threads badge: three words of five), which swipes down.

The QR page is now known by its own ids, and the share sheet needs a sheet on screen. The screens
are real dumps, anonymized: profiles, the home feed and the share sheet of Instagram 410 (French
and English), the QR page of the own profile (410 in English on a Pixel 3a, 447 in French on a
Pixel 6a, both 2026-09-27) and the options sheet of another profile (410, English, same day).
"""

import os
from pathlib import Path

import pytest
from loguru import logger

from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


OWN_PROFILE = _capture("ig410_fr_own_profile.xml")
OWN_PROFESSIONAL_PROFILE_EN = _capture("ig410_en_own_profile_professional.xml")
OTHER_PROFILE = _capture("ig410_fr_profile_follow_with_mutuals.xml")
OTHER_PROFILE_EN = _capture("ig410_en_profile_following.xml")
HOME_FEED = _capture("ig410_fr_home_feed.xml")
QR_PAGE_FR = _capture("ig447_fr_qr_page.xml")
QR_PAGE_EN = _capture("ig410_en_qr_page.xml")
SHARE_SHEET = _capture("ig410_en_share_sheet_over_sponsored_post.xml")
PROFILE_OPTIONS_SHEET = _capture("ig410_en_profile_options_sheet.xml")


class _Phone:
    """Shows a screen; any gesture brings back the screen behind it."""

    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, behind):
        self.screen, self.behind = screen, behind
        self.gestures = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def _gesture(self, name):
        self.gestures.append(name)
        self.screen = self.behind

    def press(self, key):
        self._gesture(f"press {key}")

    def swipe(self, *_a, **_k):
        self._gesture("swipe")

    def click(self, *_a, **_k):
        self._gesture("click")

    def __call__(self, **_selector):
        phone = self

        class _Missing:
            def exists(self):
                return False

            def click(self):
                phone._gesture("click")

        return _Missing()


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)


def _handle(screen, behind=HOME_FEED):
    phone = _Phone(screen, behind)
    return ProblematicPageDetector(phone).detect_and_handle_problematic_pages(), phone


@pytest.mark.parametrize("screen", [OWN_PROFILE, OWN_PROFESSIONAL_PROFILE_EN, OTHER_PROFILE,
                                    OTHER_PROFILE_EN, HOME_FEED],
                         ids=["own_profile", "own_professional_profile_en", "other_profile",
                              "other_profile_en", "home_feed"])
def test_a_profile_or_the_feed_is_left_alone(screen):
    result, phone = _handle(screen)
    assert result["detected"] is False
    assert phone.gestures == []


@pytest.mark.parametrize("screen", [QR_PAGE_FR, QR_PAGE_EN], ids=["fr_447", "en_410"])
def test_the_qr_page_is_known_by_its_ids_in_any_language_and_closed(screen):
    result, phone = _handle(screen, behind=OWN_PROFILE)
    assert result == {"detected": True, "closed": True, "soft_ban": False, "page_type": "qr_code_page"}
    assert phone.gestures == ["press back"]


def test_a_share_sheet_is_still_closed():
    result, phone = _handle(SHARE_SHEET)
    assert result["detected"] and result["closed"]
    assert phone.gestures


def test_a_profile_options_sheet_is_closed_as_a_sheet_not_as_the_qr_page():
    result, _phone = _handle(PROFILE_OPTIONS_SHEET, behind=OTHER_PROFILE)
    assert result["detected"] and result["closed"]
    assert result["page_type"] == "follow_options_bottom_sheet"


CORPUS = Path(os.environ.get("TAKTIK_DEBUG_UI") or Path(__file__).resolve().parents[5] / "debug_ui")
BASELINE = "410.0.0.53.71"


@pytest.fixture
def _quiet_detector():
    logger.disable(problematic_page.__name__)
    yield
    logger.enable(problematic_page.__name__)


@pytest.mark.skipif(not CORPUS.is_dir(), reason="no captured dumps here (they never enter the repository)")
def test_no_baseline_profile_of_the_corpus_is_a_problematic_page(_quiet_detector):
    detector = ProblematicPageDetector(device=None)
    sheets = ("bottom_sheet_container", "background_dimmer", "igds_alert_dialog_headline",
              "direct_private_share_container_view")
    profiles = 0
    for dump in sorted(CORPUS.glob(f"cartography/*/instagram/{BASELINE}/**/*.xml")):
        xml = dump.read_text(encoding="utf-8", errors="replace")
        if "profile_header_container" not in xml:
            continue
        if not problematic_page._has_surface(xml, ["profile_header_container"]):
            continue
        if problematic_page._has_surface(xml, sheets):
            continue
        profiles += 1
        found = [page for page, config in detector.detection_patterns.items() if detector._matches(xml, config)
                 and (page != "try_again_later_page" or detector._rate_limit_evidence(xml))]
        assert not found, (dump.name, found)
    if not profiles:
        pytest.skip(f"no {BASELINE} profile screen in the corpus")
