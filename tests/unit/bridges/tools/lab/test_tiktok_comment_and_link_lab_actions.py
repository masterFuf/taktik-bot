"""The TikTok comment sheet and the post link, in the Lab through the production code.

`tt.video.click_comment`, the opener of every comment test, tapped the button and called that a
success; it now opens the sheet through `CommentActions.open_comments`, which proves it came up.
`tt.comment.read` read the sheet itself, three flat lists joined by index: the pairing the
production reader dropped because one row without a body files every later comment under the
person above. It now reads through `CommentActions.read_comments`, row by row. The two production
steps of the post URL workflow, opening the video by its link (`open_post_by_url`) and reading
who commented by their handle (`CommentActions.read_commenter_handles`), had no action at all.

The sheet is a real dump of TikTok 43.1.4 in French (Pixel 3a), anonymized
(`scripts/lab/anonymize_dump.py`), read by uiautomator2's own `XPathEntry`.
"""

from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

import bridges.tools.lab.actions.tiktok.comments as comments
import bridges.tools.lab.actions.tiktok.navigation as navigation
import bridges.tools.lab.actions.tiktok.video as video
from bridges.tools.lab.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
SHEET = (FIXTURES / "tt4314_fr_comment_sheet.xml").read_text(encoding="utf-8")


class _Phone:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


class _Sheet:
    """CommentActions as the Lab action sees it: the sheet's production methods, recorded."""

    calls = []
    rows = [{"author": "a", "text": "first", "like_count": None},
            {"author": "b", "text": "", "like_count": "3"}]

    def __init__(self, device):
        self.device = device

    def _wait_for_sheet(self, timeout=6.0):
        return True

    def read_comments(self, max_comments=20):
        _Sheet.calls.append(("read_comments", max_comments))
        return list(self.rows)

    def comment_count(self):
        return 16

    def read_commenter_handles(self, max_commenters=20, *, max_scrolls=8):
        _Sheet.calls.append(("read_commenter_handles", max_commenters, max_scrolls))
        return [{"username": "laurie_b", "display_name": "Lau", "text": "hi"}]


@pytest.fixture
def sheet(monkeypatch):
    _Sheet.calls = []
    monkeypatch.setattr(comments, "CommentActions", _Sheet)
    return _Sheet


def test_the_comments_are_read_by_the_production_reader(sheet):
    result = comments.read(SimpleNamespace(device="warm"), {})

    assert sheet.calls == [("read_comments", 20)]
    assert result["success"] is True
    assert result["details"]["comments"] == [
        {"author": "a", "text": "first", "likeCount": None},
        {"author": "b", "text": "", "likeCount": "3"},
    ]
    assert result["details"]["count"] == 16


def test_each_comment_keeps_its_own_words_on_a_real_sheet():
    bundle = build_tiktok_action_bundle(create_tiktok_device_facade(_Phone(SHEET)))

    result = comments.read(bundle, {})

    assert result["success"] is True
    assert [(c["author"], c["text"]) for c in result["details"]["comments"]] == [
        ("name_14 name_15", "name_16 name_17 name_18 a dit name_19"),
        ("★", "name_16 name_23 name_24 name_25, name_26 name_27 name_28"),
    ]


def test_a_closed_sheet_is_not_read(monkeypatch):
    class Closed(_Sheet):
        def _wait_for_sheet(self, timeout=6.0):
            return False

    monkeypatch.setattr(comments, "CommentActions", Closed)
    Closed.calls = []

    result = comments.read(SimpleNamespace(device="warm"), {})

    assert result["success"] is False
    assert result["details"] == {"sheetOpen": False}
    assert Closed.calls == []


def test_the_commenters_are_read_by_their_handle_as_the_post_url_workflow_does(sheet):
    result = comments.read_commenter_handles(SimpleNamespace(device="warm"),
                                             {"max_commenters": "4", "max_scrolls": "1"})

    assert sheet.calls == [("read_commenter_handles", 4, 1)]
    assert result["success"] is True
    assert result["details"]["commenters"] == [{"username": "laurie_b", "displayName": "Lau"}]


def test_a_video_is_opened_by_its_link_through_the_production_opener(monkeypatch):
    calls = []
    monkeypatch.setattr(navigation, "open_post_by_url",
                        lambda device, url, **kwargs: calls.append((device, url, kwargs)) or True)

    result = navigation.open_post_url(SimpleNamespace(device="warm"), {"post_url": " https://vm.tiktok.com/x/ "})

    assert calls == [("warm", "https://vm.tiktok.com/x/", {})]
    assert result["success"] is True


def test_no_link_opens_nothing(monkeypatch):
    monkeypatch.setattr(navigation, "open_post_by_url",
                        lambda *_a, **_k: pytest.fail("opened without a link"))

    assert navigation.open_post_url(SimpleNamespace(device="warm"), {})["success"] is False


# The opener of the sheet, the context every comment test runs in: production opens it through
# `CommentActions.open_comments`, which proves the sheet came up. The Lab tapped the button through
# `VideoActions.click_comment_button`, which no workflow calls, and called a tap that opened nothing
# a success.


def test_the_sheet_is_opened_by_the_production_opener(monkeypatch):
    opened = []

    class _Opener(_Sheet):
        def open_comments(self):
            opened.append(self.device)
            return True

    monkeypatch.setattr(video, "CommentActions", _Opener)
    bundle = SimpleNamespace(device="warm", video_detector=SimpleNamespace(is_live_preview=lambda: False),
                             video=SimpleNamespace(click_comment_button=lambda: pytest.fail("bare tap")))

    assert video.click_comment(bundle, {}) is True
    assert opened == ["warm"]


def test_a_live_preview_has_no_sheet_to_open(monkeypatch):
    monkeypatch.setattr(video, "CommentActions", lambda device: pytest.fail("opened on a LIVE"))
    bundle = SimpleNamespace(device="warm", video_detector=SimpleNamespace(is_live_preview=lambda: True))

    result = video.click_comment(bundle, {})

    assert result["success"] is False
    assert "not_applicable" in result["details"]
