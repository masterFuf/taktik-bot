"""TikTok's "update the app" prompt exposes no readable node: it is found by its shape in the
dump, read by OCR, and dismissed on its "not now" word only.

Screens and OCR results are invented; the shape follows the 43.1.4 capture (app nodes with no
text or content-desc, a centred dialog frame).
"""

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

APP = "com.zhiliaoapp.musically"


def _node(bounds, package=APP, text="", desc=""):
    return (f'<node class="android.widget.FrameLayout" package="{package}" text="{text}" '
            f'content-desc="{desc}" resource-id="" bounds="{bounds}">')


def _screen(*nodes):
    closing = "</node>" * len(nodes)
    status = '<node class="android.widget.TextView" package="com.android.systemui" text="00:50" content-desc="00:50" bounds="[50,0][161,66]"/>'
    return f'<hierarchy rotation="0">{status}{"".join(nodes)}{closing}</hierarchy>'


PROMPT = _screen(_node("[0,0][1080,2220]"), _node("[0,0][1080,2220]"), _node("[152,562][928,1658]"))
SPLASH = _screen(_node("[0,0][1080,2220]"), _node("[0,0][1080,2220]"))
FEED = _screen(_node("[0,0][1080,2220]"), _node("[152,562][928,1658]", desc="Pour toi"))
LAUNCHER_ONLY = _screen()


def test_the_prompt_is_found_by_its_shape():
    assert unlabelled_overlay_region(parse_ui_dump(PROMPT)) == (152, 562, 928, 1658)


@pytest.mark.parametrize("xml", [SPLASH, FEED, LAUNCHER_ONLY])
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


LOADING_LOGO = _screen(_node("[0,0][1080,2220]"), _node("[0,0][1080,2220]"), _node("[498,1192][582,1276]"))
BOTTOM_SHEET = _screen(_node("[0,0][1080,2220]"), _node("[0,1200][1080,2220]"))


@pytest.mark.parametrize("xml", [LOADING_LOGO, BOTTOM_SHEET])
def test_a_small_logo_or_an_edge_sheet_is_not_a_dialog(xml):
    assert unlabelled_overlay_region(parse_ui_dump(xml)) is None
