"""The comment sheet is still recognised once its build ids move, and never on the video screen.

`COMMENT_SELECTORS.sheet_indicator` rested on the sheet panel ids only (`maf`/`h7t` on 43.1.4,
`o3y`/`ieb` on 46.6.3). Build ids move with every version (the composer went `dpl` -> `egn`
between those two), and no sheet of a later version is captured. When they go, the sheet reads
as closed and every comment action refuses.

The locale route behind them: the sheet's close control, on a screen showing the sheet's composer
(clickable, with its hint) or its count header. The failure it must never have is the one the
composer affordances had: answering yes on the VIDEO screen, whose comment bar carries the same
hint but is not clickable.

Screens: extracts of captures (43.1.4 and 46.6.3 sheets, full, empty and with typed text; the
English sheet of 43.1.4; the video page of 47.0.3), anonymized: structure, ids and bounds of the
capture, comment rows left out. `_next_build` renames the build ids the way a version bump does.
Evaluated by uiautomator2's own `d.xpath()` engine through `first_matching`, as
`CommentActions.is_comment_sheet_open` reads it.
"""

import re

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import COMMENT_SELECTORS

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


def _sheet_43_1_4(close="Fermer", sort="Trier", header="‎12 commentaires",
                  hint="Ajouter un commentaire…"):
    """TikTok 43.1.4 sheet: panel `h7t`/`maf`, header row `doj` with sort and close, count `tmr`."""
    return _screen(_node("android.widget.LinearLayout", "npl", clickable=True, bounds="[0,0][1080,2088]", children=(
        _node("android.view.View", "drk", clickable=True, bounds="[0,0][1080,669]")
        + _node("android.widget.FrameLayout", "h7t", bounds="[0,669][1080,2088]", children=(
            _node("android.widget.LinearLayout", "maf", bounds="[0,669][1080,2088]", children=(
                _node("android.widget.FrameLayout", "drm", bounds="[0,785][1080,905]", children=_node(
                    "android.widget.LinearLayout", "tms", clickable=True, bounds="[0,785][1080,905]",
                    children=_node("android.widget.TextView", "tmr", header, bounds="[369,785][711,905]")))
                + _node("android.view.ViewGroup", "dpj", bounds="[0,1927][1080,2088]", children=_node(
                    "android.widget.EditText", "dpl", hint, clickable=True, bounds="[199,1949][704,2030]",
                    hint=hint))))
            + _node("android.widget.RelativeLayout", "doj", bounds="[33,669][1047,801]", children=(
                _node("android.widget.FrameLayout", "dr4", bounds="[33,669][992,801]")
                + _node("android.widget.ImageView", "dse", desc=sort, clickable=True, bounds="[832,674][953,795]")
                + _node("android.widget.ImageView", "b9b", desc=close, clickable=True,
                        bounds="[992,707][1047,762]"))))))))


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


def _video_page_47_0_3(extra=""):
    """TikTok 47.0.3 video opened from search: its comment bar `ejs` is NOT clickable (the View
    `mzp` above it takes the tap) and carries the composer's hint. The row beside it is given the
    composer affordances' labels, which the video screen is known to show."""
    return _screen(
        _node("android.widget.Button", desc="Lire ou ajouter des commentaires. 6 commentaires",
              clickable=True, bounds="[954,1500][1080,1640]")
        + _node("android.widget.FrameLayout", "ejr", bounds="[0,2208][1080,2337]", children=_node(
            "android.view.ViewGroup", "ejq", bounds="[0,2208][1080,2337]", children=(
                _node("android.view.View", "mzp", clickable=True, bounds="[32,2218][1048,2334]")
                + _node("android.widget.EditText", "ejs", "Ajouter un commentaire…",
                        bounds="[64,2219][1037,2300]", hint="Ajouter un commentaire…")
                + _node("android.widget.LinearLayout", "kjk", bounds="[732,2228][1032,2323]", children=(
                    _node("android.widget.Button", "l12", desc="Mentionne quelqu'un", clickable=True)
                    + _node("android.widget.ImageView", "m4_", desc="Stickers", clickable=True)))))) + extra)


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
    found = first_matching(_Device(_sheet_43_1_4()), COMMENT_SELECTORS.sheet_indicator)
    assert found and found[0].attrib.get("resource-id") == ID + "maf"
    found = first_matching(_Device(_sheet_46_6_3()), COMMENT_SELECTORS.sheet_indicator)
    assert found and found[0].attrib.get("resource-id") == ID + "o3y"


@pytest.mark.parametrize("xml", [
    _sheet_43_1_4(), _sheet_46_6_3(), _sheet_46_6_3(empty=True), _sheet_46_6_3(typed="texte"),
], ids=["43.1.4", "46.6.3", "46.6.3-empty", "46.6.3-typed"])
def test_a_sheet_whose_build_ids_moved_is_still_open(french, xml):
    """Panel ids gone: the full sheet, the empty one (no count header) and the one with typed text
    (the hint is gone) are each seen by one half of the route."""
    assert _open(_next_build(xml))


def test_the_english_sheet_is_seen_too(english):
    xml = _sheet_43_1_4(close="Close", sort="Sort", header="‎1 comment", hint="Add comment...")
    assert _open(_next_build(xml))


@pytest.mark.parametrize("extra", [
    "",
    _node("android.widget.ImageView", "b9b", desc="Fermer", clickable=True, bounds="[992,707][1047,762]"),
], ids=["video-page", "video-page-with-a-close-control"])
def test_the_video_screen_is_never_an_open_sheet(french, extra):
    """The bar carries the composer's hint and the affordances sit beside it. Even with a close
    control on another layer, the sheet reads closed: the bar is not clickable and there is no
    count header."""
    assert not _open(_video_page_47_0_3(extra))
    assert not _open(_next_build(_video_page_47_0_3(extra)))
