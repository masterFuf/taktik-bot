"""TikTok's "update the app" prompt exposes no readable node: it is found by its shape in the
dump, read by OCR, and dismissed on its "not now" word only.

The prompt is the real 43.1.4 capture (Pixel 3a, French), anonymized: app nodes with no text or
content-desc, a centred dialog frame. So are the For You feed of the same version, the Pixel
launcher (Android 12, French) and two real cold-start captures of TikTok's launch screen: a
starting window on the Pixel 4a that exposes no app node at all, before the first labelled screen
(`tt4314_fr_launch_starting_window.xml`), and, captured on the Pixel 3a right after a force-stop
(decision D16 of 2026-09-27), a black screen where uiautomator sees no node of the app either, only
the status bar (`tt4314_fr_launch_black.xml`); dumped every 0.07 s from the launch, the 3a went
from it straight to the feed, with no loading logo in between. No capture shows an unlabelled
loading logo, an unlabelled sheet, or a page of empty full-screen frames: those three are the real
prompt with its dialog frame moved (derived, said below), since the frame's geometry is all the
detector reads. The OCR results are invented.
"""

from pathlib import Path

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.shared.vision.ocr import TextMatch
from taktik.core.social_media.tiktok.actions.atomic.interaction.popup_actions import PopupActions
from taktik.core.social_media.tiktok.actions.business.workflows._internal import popup_handler
from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import (
    PopupHandler,
    unlabelled_overlay_region,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.shell.popups import POPUP_SELECTORS

FIXTURES = Path(__file__).parent / "fixtures"
PROMPT = (FIXTURES / "tt4314_fr_update_prompt.xml").read_text(encoding="utf-8")
SPLASH = (FIXTURES / "tt4314_fr_launch_starting_window.xml").read_text(encoding="utf-8")
SPLASH_BLACK = (FIXTURES / "tt4314_fr_launch_black.xml").read_text(encoding="utf-8")
PROMPT_FRAME = 'bounds="[152,562][928,1658]"'


def _prompt_with_frame(bounds):
    """The real prompt, its dialog frame (two nested nodes) moved to ``bounds`` (derived)."""
    assert PROMPT.count(PROMPT_FRAME) == 2
    return PROMPT.replace(PROMPT_FRAME, f'bounds="{bounds}"')


#: Empty frames over the whole screen, the page a loading app shows before its content.
EMPTY_PAGE = _prompt_with_frame("[0,0][1080,2220]")
FEED = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
LAUNCHER_ONLY = (Path(__file__).parents[2] / "shared" / "device" / "fixtures"
                 / "android12_fr_launcher_home.xml").read_text(encoding="utf-8")


def test_the_prompt_is_found_by_its_shape():
    assert unlabelled_overlay_region(parse_ui_dump(PROMPT)) == (152, 562, 928, 1658)


@pytest.mark.parametrize("xml", [SPLASH, SPLASH_BLACK, EMPTY_PAGE, FEED, LAUNCHER_ONLY],
                         ids=["splash", "splash_black", "empty_page", "feed", "launcher"])
def test_a_screen_that_is_not_the_prompt_is_left_alone(xml):
    assert unlabelled_overlay_region(parse_ui_dump(xml)) is None


def _match(word, top):
    return TextMatch(text=word, confidence=95, left=470, top=top, width=220, height=32)


class _Device:
    def __init__(self):
        self.taps = []

    def human_tap(self, bounds, **_):
        self.taps.append(bounds)
        return (bounds[0], bounds[1])


def _actions(monkeypatch, ocr_words):
    import taktik.core.shared.vision.screen_text as screen_text

    calls = []

    def locate(device, queries, region=None, **_):
        calls.append((list(queries), region))
        return list(ocr_words)

    monkeypatch.setattr(screen_text, "locate_text_on_screen", locate)
    actions = object.__new__(PopupActions)
    actions.popup_selectors = POPUP_SELECTORS
    actions.device = _Device()
    return actions, calls


@pytest.fixture
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_not_now_is_tapped_when_the_title_is_read_too(monkeypatch, french):
    actions, calls = _actions(monkeypatch, [_match("application", 800), _match("maintenant.", 1558)])
    assert actions.dismiss_update_prompt((152, 562, 928, 1658))
    assert actions.device.taps == [(470, 1558, 690, 1590)]
    assert calls[0][1] == (152, 562, 928, 1658)


@pytest.mark.parametrize("words", [[_match("maintenant", 1558)], [_match("application", 800)], []])
def test_nothing_is_tapped_without_both_words(monkeypatch, french, words):
    actions, _ = _actions(monkeypatch, words)
    assert not actions.dismiss_update_prompt(None)
    assert actions.device.taps == []


def test_a_locale_without_the_words_never_reads_the_screen(monkeypatch):
    set_active_locale("en")
    try:
        actions, calls = _actions(monkeypatch, [_match("application", 800), _match("maintenant", 1558)])
        assert not actions.dismiss_update_prompt(None)
        assert calls == []
    finally:
        set_active_locale(None)


class _Detection:
    def __init__(self, xml):
        self.device = type("D", (), {"dump_hierarchy": lambda self, **_: xml})()


class _Click:
    def __init__(self):
        self.regions = []

    def dismiss_update_prompt(self, region):
        self.regions.append(region)
        return True


def test_the_chain_dismisses_the_prompt_and_waits_before_trying_again(monkeypatch):
    monkeypatch.setattr(popup_handler.time, "sleep", lambda _s: None)
    click = _Click()
    handler = PopupHandler(click, _Detection(PROMPT))
    assert handler.close_all()
    assert click.regions == [(152, 562, 928, 1658)]
    assert not handler.close_all()
    assert len(click.regions) == 1


def test_a_normal_screen_never_reaches_the_ocr():
    click = _Click()
    assert not PopupHandler(click, _Detection(FEED)).close_all()
    assert click.regions == []


#: A logo on an empty page, and a sheet anchored to the bottom edge: the real prompt's frame
#: shrunk to a logo in the middle, or stretched to the bottom edge (derived).
LOADING_LOGO = _prompt_with_frame("[498,1068][582,1152]")
BOTTOM_SHEET = _prompt_with_frame("[0,1200][1080,2220]")


@pytest.mark.parametrize("xml", [LOADING_LOGO, BOTTOM_SHEET], ids=["loading_logo", "bottom_sheet"])
def test_a_small_logo_or_an_edge_sheet_is_not_a_dialog(xml):
    assert unlabelled_overlay_region(parse_ui_dump(xml)) is None
