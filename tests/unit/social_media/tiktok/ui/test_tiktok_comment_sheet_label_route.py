"""The comment sheet is still recognised once its build ids move, and never on the video screen.

`COMMENT_SELECTORS.sheet_indicator` rested on the sheet panel ids only (`maf`/`h7t` on 43.1.4,
`o3y`/`ieb` on 46.6.3). Build ids move with every version (the composer went `dpl` -> `egn`
between those two), and no sheet of a later version is captured. When they go, the sheet reads
as closed and every comment action refuses.

The locale route behind them: the sheet's labelled close control beside the sheet's composer
(its hint), or its count header beside a clickable composer. The failure it must never have is the
one the composer affordances had: answering yes on the VIDEO screen, whose comment bar carries the
same hint but is not clickable. The close control is what tells them apart, not the composer's
clickability: once Back has closed the keyboard the sheet's own composer is not clickable either
(the empty sheet of 43.1.4).

Screens, anonymized: the sheet of 43.1.4 in French, full (Pixel 3a, `tt-3a-fr`) and empty (Pixel
3a, 2026-09-27, opened on a video with no comment, its keyboard closed by Back), a 43.1.4 video opened from
the profile, whose comment bar IS clickable and carries the composer's hint (Pixel 3a, same day),
the video page of 47.0.3 opened from search, whose bar is not clickable (Pixel 6a, 2026-09-25),
and the 47.0.3 sheet as a phone showed it (`fixtures/tt4703_fr_comment_sheet.xml`: its close
control carries no label at all and its header reads « ‎N commentaires »). Derived, and said: the
English sheet is the French 43.1.4 capture with the English labels of 43.1.4 (« Close », « Add
comment... », « ‎N comments »), measured on a capture the corpus no longer holds. The 46.6.3 sheets
(full, empty, with typed text) are still rebuilt by hand after their captures: no phone runs 46.6.3.
`_next_build` renames the build ids the way a version bump does. Evaluated by uiautomator2's own
`d.xpath()` engine through `first_matching`, as `CommentActions.is_comment_sheet_open` reads it.
"""

import re

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.shell.popups import POPUP_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import COMMENT_SELECTORS
from unit.paths import CORE

ID = "com.zhiliaoapp.musically:id/"


def _node(cls, rid="", text="", desc="", clickable=False, bounds="[0,0][1,1]", hint=None, children=""):
    head = (f'class="{cls}" resource-id="{rid and ID + rid}" text="{text}" content-desc="{desc}" '
            f'clickable="{str(clickable).lower()}" bounds="{bounds}"')
    if hint is not None:
        head += f' hint="{hint}"'
    return f"<node {head}>{children}</node>" if children else f"<node {head}/>"


def _screen(*body):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">{"".join(body)}</node>'
            "</hierarchy>")


def _next_build(xml):
    """Every obfuscated build id renamed, readable ids (`message_tv`) kept."""
    return re.sub(r":id/([a-z0-9_]{2,4})\"", lambda m: f':id/q{m.group(1)}9"', xml)


FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


SHEET_4314 = _capture("tt4314_fr_comment_sheet.xml")
SHEET_4314_EMPTY = _capture("tt4314_fr_comment_sheet_empty.xml")
VIDEO_4314 = _capture("tt4314_fr_liked_video.xml")
VIDEO_4703 = _capture("tt4703_fr_video_page_comment_bar.xml")


def _in_english(xml):
    """The French 43.1.4 sheet with the English labels of 43.1.4."""
    return (xml.replace('content-desc="Fermer"', 'content-desc="Close"')
            .replace("Ajouter un commentaire…", "Add comment...")
            .replace("\u200e50 commentaires", "\u200e50 comments"))


def _sheet_46_6_3(empty=False, typed=""):
    """TikTok 46.6.3 sheet: panel `ieb`/`o3y`, close `bqo`, count `w5r` (absent when empty)."""
    header = "" if empty else _node("android.widget.LinearLayout", "w5s", clickable=True,
                                     bounds="[0,878][1080,994]", children=_node(
        "android.widget.TextView", "w5r", "‎12 commentaires", bounds="[308,878][676,994]"))
    body = _node("android.widget.TextView", "message_tv", "Les commentaires apparaissent ici",
                 bounds="[250,1474][830,1521]") if empty else ""
    hint = "" if typed else "Ajouter un commentaire…"
    return _screen(_node("android.widget.LinearLayout", "pp2", clickable=True, bounds="[0,0][1080,2400]", children=(
        _node("android.view.View", "ej_", clickable=True, bounds="[0,0][1080,768]")
        + _node("android.widget.FrameLayout", "ieb", bounds="[0,768][1080,2400]", children=_node(
            "android.widget.LinearLayout", "o3y", bounds="[0,768][1080,2400]", children=(
                _node("android.widget.FrameLayout", "eja", bounds="[0,768][1080,894]", children=(
                    header
                    + _node("android.widget.RelativeLayout", "efl", bounds="[0,768][1048,884]", children=(
                        _node("android.widget.FrameLayout", "ei9", bounds="[0,768][995,884]")
                        + _node("android.widget.ImageView", "bqo", desc="Fermer", clickable=True,
                                bounds="[995,799][1048,852]")))))
                + _node("android.view.ViewGroup", "wur", bounds="[0,1103][1080,1891]", children=body or _node(
                    "android.view.View"))
                + _node("android.view.ViewGroup", "egl", bounds="[0,1217][1080,1433]", children=_node(
                    "android.widget.EditText", "egn", typed or hint, clickable=True,
                    bounds="[189,1238][1011,1378]", hint=hint))))))))


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml


@pytest.fixture
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


def _open(xml):
    return bool(first_matching(_Device(xml), COMMENT_SELECTORS.sheet_indicator))


def test_the_measured_versions_still_answer_from_the_panel(french):
    """43.1.4 and 46.6.3: the panel id wins first, exactly as before."""
    found = first_matching(_Device(SHEET_4314), COMMENT_SELECTORS.sheet_indicator)
    assert found and found[0].attrib.get("resource-id") == ID + "maf"
    found = first_matching(_Device(_sheet_46_6_3()), COMMENT_SELECTORS.sheet_indicator)
    assert found and found[0].attrib.get("resource-id") == ID + "o3y"


@pytest.mark.parametrize("xml", [
    SHEET_4314, SHEET_4314_EMPTY,
    _sheet_46_6_3(), _sheet_46_6_3(empty=True), _sheet_46_6_3(typed="texte"),
], ids=["43.1.4", "43.1.4-empty-keyboard-closed", "46.6.3", "46.6.3-empty", "46.6.3-typed"])
def test_a_sheet_whose_build_ids_moved_is_still_open(french, xml):
    """Panel ids gone: the full sheet, the empty ones (no count header; on 43.1.4 the composer no
    longer clickable once Back has closed the keyboard) and the one with typed text (the hint is
    gone) are each seen by one half of the route."""
    assert _open(_next_build(xml))


def test_the_empty_sheet_of_43_1_4_has_no_clickable_composer():
    """What the route must not require: on the real empty sheet the composer (`EditText` with the
    hint) is not clickable, and there is no count header."""
    [composer] = etree.fromstring(SHEET_4314_EMPTY.encode("utf-8")).xpath(
        '//node[@class="android.widget.EditText"]')
    assert composer.get("hint").startswith("Ajouter un commentaire")
    assert composer.get("clickable") == "false"
    assert "‎" not in SHEET_4314_EMPTY and 'text="Commentaires"' in SHEET_4314_EMPTY


SHEET_4703 = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4703_fr_comment_sheet.xml").read_text(
    encoding="utf-8")


def test_the_47_0_3_sheet_is_open(french):
    """No panel id of the base, no labelled close control: the count header answers, read
    through its U+200E, with the sheet's composer clickable on screen."""
    found = first_matching(_Device(SHEET_4703), COMMENT_SELECTORS.sheet_indicator)
    assert found and found[0].attrib.get("resource-id") == ID + "wk7"


@pytest.mark.parametrize("selectors", [
    lambda: POPUP_SELECTORS.comments_close_button,
    lambda: COMMENT_SELECTORS.close_button,
], ids=["popup.comments_close_button", "comment.close_button"])
def test_the_47_0_3_close_control_is_found_without_a_label(french, selectors):
    """47.0.3 labels its close control with nothing: the clickable ImageView of the row that
    follows the count header's row. Both closers must reach it, not fall back on Back."""
    found = first_matching(_Device(SHEET_4703), selectors())
    assert [el.attrib.get("resource-id") for el in found] == [ID + "bs4"]


def test_the_47_0_3_screen_without_a_clickable_composer_is_not_a_sheet(french):
    """The same screen with its composer in the state of the video page's bar (same id `ejs`,
    not clickable): the header alone does not make it a sheet."""
    bar = re.sub(r'(resource-id="[^"]*:id/ejs"[^>]*?)clickable="true"', r'\1clickable="false"',
                 SHEET_4703)
    assert bar != SHEET_4703
    assert not _open(bar)


@pytest.mark.parametrize("sheet", [SHEET_4314, SHEET_4314_EMPTY], ids=["43.1.4", "43.1.4-empty-keyboard-closed"])
def test_the_english_sheet_is_seen_too(english, sheet):
    xml = _in_english(sheet)
    assert xml != sheet and 'content-desc="Fermer"' not in xml and "Add comment..." in xml
    assert _open(_next_build(xml))


@pytest.mark.parametrize("xml", [VIDEO_4703, VIDEO_4314], ids=["47.0.3-bar-not-clickable",
                                                             "43.1.4-bar-clickable"])
def test_the_video_screen_is_never_an_open_sheet(french, xml):
    """The bar carries the composer's hint and the affordances sit beside it; on 43.1.4 it is even
    clickable. The sheet reads closed: there is no close control of a sheet and no count header."""
    assert "Ajouter un commentaire…" in xml
    assert not _open(xml)
    assert not _open(_next_build(xml))
