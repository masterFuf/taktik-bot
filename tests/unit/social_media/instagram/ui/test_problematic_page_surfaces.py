"""A profile is never a problematic page; the pages themselves still are.

Opening the connected account's own profile, the detector found the label of the profile's
own share button, called the screen `qr_code_page` (one word of three was its threshold) and
pressed Back: the profile was left before its counters were read. With that pattern narrowed,
the same profile fell to `profile_share_page` (its avatar's story badge, its share button and
its Threads badge: three words of five), which swipes down.

The QR page is now known by its own ids, and the share sheet needs a sheet on screen. The
screens below keep the ids, nesting and interface labels of real IG 410 captures; names and
texts are invented.
"""

import os
from pathlib import Path

import pytest
from loguru import logger

from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector

ID = "com.instagram.android:id/"


def _node(rid="", text="", desc="", cls="android.view.View", bounds="[0,0][1,1]", children=""):
    rid = f"{ID}{rid}" if rid else ""
    return (f'<node text="{text}" resource-id="{rid}" class="{cls}" package="com.instagram.android" '
            f'content-desc="{desc}" bounds="{bounds}">{children}</node>')


def _screen(*nodes):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            + _node(cls="android.widget.FrameLayout", bounds="[0,0][1080,2160]", children="".join(nodes))
            + "</hierarchy>")


def _tab_bar():
    return _node("tab_bar", cls="android.widget.LinearLayout", bounds="[0,1907][1080,2028]", children=(
        _node("feed_tab", desc="Home", cls="android.widget.FrameLayout", bounds="[0,1907][216,2028]")
        + _node("profile_tab", desc="Profil", cls="android.widget.FrameLayout", bounds="[864,1907][1080,2028]")))


def _profile(buttons, bio="", badge=""):
    return _screen(
        _node("action_bar_title", text="demo.account", desc="demo.account", cls="android.widget.TextView"),
        _node("profile_header_container", cls="android.widget.LinearLayout", children=(
            badge
            + _node("profile_header_familiar_post_count_value", text="12", cls="android.widget.TextView")
            + _node("profile_header_familiar_post_count_label", text="publications", cls="android.widget.TextView")
            + (_node(text=bio, cls="android.widget.TextView") if bio else "")
            + "".join(_node("button_container", desc=label, cls="android.widget.Button",
                            children=_node(text=label, cls="android.widget.TextView"))
                      for label in buttons))),
        _tab_bar())


OWN_PROFILE = _profile(
    ("Modifier le profil", "Partager le profil"),
    badge=(_node("reel_empty_badge", desc="Ajouter à la story", cls="android.widget.ImageView")
           + _node(desc="Voir le profil sur Threads", cls="android.widget.ImageView")))

OTHER_PROFILE = _profile(("Suivre", "Envoyer un message"),
                         bio="Scannez mon QR code en boutique et copiez le lien du menu")

HOME_FEED = _screen(
    _node("reels_tray_container", children=_node(desc="Ajouter à la story", cls="android.widget.Button")),
    _node("row_feed_photo_profile_name", text="someone.else", cls="android.widget.TextView"),
    _node(text="Mon dernier post est aussi sur Threads", cls="android.widget.TextView"),
    _tab_bar())


def _qr_page(share, copy, close):
    return _screen(_node("nametag_container", cls="android.widget.FrameLayout", children=(
        _node("card_view", desc="@2131975091")
        + _node("profile_share_card", cls="android.widget.LinearLayout", children=(
            _node("profile_share_card_share_button", cls="android.widget.LinearLayout",
                  children=_node(desc=share, cls="android.widget.ImageView") + _node(text=share, cls="android.widget.TextView"))
            + _node("profile_share_card_copy_link_button", cls="android.widget.LinearLayout",
                    children=_node(desc=copy, cls="android.widget.ImageView") + _node(text=copy, cls="android.widget.TextView"))))
        + _node("close_button", desc=close, cls="android.widget.ImageView"))))


QR_PAGE_FR = _qr_page("Partager le profil", "Copier le lien", "Fermer")
QR_PAGE_EN = _qr_page("Share profile", "Copy link", "Close")

SHARE_SHEET = _screen(_node("direct_private_share_container_view", children=(
    _node("direct_external_share_container_view", children="".join(
        _node("direct_external_reshare_row", text=label, cls="android.widget.Button")
        for label in ("Ajouter à la story", "WhatsApp", "Partager", "Texto", "Threads")))
    + _node(text="Écrivez un message…", cls="android.widget.EditText"))))

PROFILE_OPTIONS_SHEET = _screen(
    _node("profile_header_container", cls="android.widget.LinearLayout"),
    _node("bottom_sheet_container", children=(
        _node("background_dimmer", desc="@2131954950")
        + "".join(_node("action_sheet_row_text_view", text=label, cls="android.widget.TextView")
                  for label in ("Envoyer à…", "Copier le lien", "Afficher le code QR", "Partager sur…")))))


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


@pytest.mark.parametrize("screen", [OWN_PROFILE, OTHER_PROFILE, HOME_FEED],
                         ids=["own_profile", "other_profile", "home_feed"])
def test_a_profile_or_the_feed_is_left_alone(screen):
    result, phone = _handle(screen)
    assert result["detected"] is False
    assert phone.gestures == []


@pytest.mark.parametrize("screen", [QR_PAGE_FR, QR_PAGE_EN], ids=["fr", "en"])
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
