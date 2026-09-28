"""Instagram's one-dump readers read a screen photo (steps 3 L5-L6 of the one-photo spec).

`batch_xpath_check` (screen signals, profile flags) and the profile readers asked their selectors
of plain lxml on `parse_ui_dump`: the right tree, but not the path `d.xpath()` takes behind the
`CloneAwareDeviceProxy` every Instagram bridge mounts. An id equality missed a clone's prefix and a
Compose screen's bare id, and a uiautomator2 shorthand was rejected. They now ask a photo, which
answers as `d.xpath()` does through the proxy, still on one dump. The readers that walk the tree
get the photo's tree: the same nodes as before, taken through the facade.

The screens are real captures, anonymized: a visited professional profile (Instagram 410, French:
category line, bio cut by « … plus », website, a linked-account banner), a profile whose bio is
cut, and the notifications list (Pixel 4a, 2026-09-28), whose ids are bare. A clone's screen is
the real profile with the clone's package in place of Instagram's (derived: no clone is installed
on the phones of the bench). An empty hierarchy is not a screen: it is what the device answers
when it cannot read one.
"""

from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    ProfileExtractionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS

STOCK = "com.instagram.android"
CLONE = "com.taktik.ig1"
FIXTURES = Path(__file__).parent / "fixtures"
EMPTY = '<hierarchy rotation="0" />'


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _profile(package: str) -> str:
    """A visited professional profile, its ids under `package` (a clone renames the prefix)."""
    return _capture("ig410_fr_profile_highlights_only.xml").replace(STOCK, package)


class _Phone:
    """uiautomator2 as far as these readers touch it: dumps (counted) and a screenshot."""

    def __init__(self, xml):
        self.xml = xml
        self.dumps = 0

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        return self.xml

    def screenshot(self, *_a, **_k):
        return Image.new("RGB", (1080, 2400), color=(10, 20, 30))


def _facade(xml, proxy=True):
    phone = _Phone(xml)
    return DeviceFacade(CloneAwareDeviceProxy(phone, STOCK) if proxy else phone), phone


class _Reader(ProfileExtractionMixin):
    def __init__(self, device):
        self.device = device
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = PROFILE_SELECTORS

        class _Quiet:
            def debug(self, *a, **k):
                return None

            info = warning = error = debug

        self.logger = _Quiet()


# --------------------------------------------------------------------------- batch_xpath_check

def test_the_batch_check_is_one_photo_answered_through_the_proxy():
    """An id equality now finds a clone's prefix and a bare id, as `d.xpath()` behind the proxy
    does; plain lxml on the dump found neither."""
    clone, phone = _facade(_profile(CLONE))
    assert f'{STOCK}:id/' not in phone.xml
    assert clone.batch_xpath_check({
        "clone": [f'//*[@resource-id="{STOCK}:id/profile_header_container"]'],
        "absent": [f'//*[@resource-id="{STOCK}:id/row_feed_button_like"]'],
    }) == {"clone": True, "absent": False}
    assert phone.dumps == 1

    notifications = _capture("ig410_fr_notifications_rows.xml")
    assert 'resource-id="activity_feed_list"' in notifications
    bare, phone = _facade(notifications)
    assert bare.batch_xpath_check({"bare": [f'//*[@resource-id="{STOCK}:id/activity_feed_list"]']}) == {"bare": True}
    assert phone.dumps == 1


def test_the_batch_check_reads_shorthands_and_skips_a_rejected_selector():
    facade, _phone = _facade(_profile(STOCK))
    assert facade.batch_xpath_check({"title": ["//*[", f"@{STOCK}:id/action_bar_title"]}) == {"title": True}


# « ERROR: could not get idle state. » is what uiautomator printed instead of a dump on 2026-09-26.
@pytest.mark.parametrize("xml", [EMPTY, "", "ERROR: could not get idle state."])
def test_an_unreadable_screen_answers_false_for_every_name(xml):
    facade, phone = _facade(xml)
    assert facade.batch_xpath_check({"a": ["//*"], "b": ["//node"]}) == {"a": False, "b": False}
    assert phone.dumps == 1


# --------------------------------------------------------------------------- profile readers

#: The bio of the real profile, as the dump carries it: two bullet lines, cut by « … plus ».
BIO = ("• name_5 Privé à name_6, name_7, name_8 ..\n• name_9 name_10 : \n-@user_4 -code name_11: "
       "user_5 :       -… plus")


def _read_all(package):
    facade, phone = _facade(_profile(package))
    reader = _Reader(facade)
    enriched = reader.get_enriched_profile_data()
    return {
        "flags": reader.get_profile_flags_batch(),
        "text": reader.get_profile_text_batch(),
        "enriched": {k: v for k, v in enriched.items() if not k.startswith("_")},
        "avatar": reader.extract_profile_image() is not None,
    }, phone


def test_the_profile_readers_read_the_stock_header():
    answers, phone = _read_all(STOCK)
    assert answers["flags"] == {"is_private": False, "is_verified": False, "is_business": True}
    assert answers["text"] == {"username": "name_1", "full_name": "name_2 name_3", "biography": BIO}
    assert answers["enriched"]["business_category"] == "name_4"
    assert answers["enriched"]["website"] == "user_6/name_12/"
    assert answers["enriched"]["linked_accounts"] == [{"name": "name_2 name_13", "platform": "unknown"}]
    assert answers["enriched"]["bio_truncated"] is True
    assert answers["avatar"] is True
    assert phone.dumps == 4  # one photo per reader call


def test_a_clone_reads_like_the_stock_app():
    """Behind the proxy, a clone's header answers as the stock one: every equality of these
    readers used to miss the clone's prefix."""
    assert _read_all(CLONE)[0] == _read_all(STOCK)[0]


@pytest.mark.parametrize("name, region", [
    ("ig410_fr_profile_highlights_only.xml", (44, 543, 933, 680)),
    ("ig410_fr_profile_bio_truncated.xml", (44, 494, 772, 675)),
])
def test_the_bounded_bio_read_is_one_dump_through_the_timeout(name, region):
    """Two real bios cut by « … plus »: the region is the bio node's own bounds."""
    facade, phone = _facade(_capture(name))
    calls = []
    real = facade.get_xml_dump

    def bounded(timeout_seconds=None):
        calls.append(timeout_seconds)
        return real()

    facade.get_xml_dump = bounded
    assert _Reader(facade)._truncated_bio_region() == region
    assert calls == [5.0] and phone.dumps == 1


# --------------------------------------------------------------------------- tree walkers

def _walkers(facade):
    from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
    from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
    from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions import (
        FeedSuggestionsMixin,
    )
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )

    class _Log:
        def debug(self, *a, **k):
            return None

        error = debug

    reading = object.__new__(PostReadingMixin)
    comment = object.__new__(CommentAction)
    suggestions = object.__new__(FeedSuggestionsMixin)
    for host in (reading, comment, suggestions):
        host.device, host.logger = facade, _Log()
    notifications = NotificationsEngagementWorkflow(facade, "test")
    return {
        "post reading": reading._dump_root,
        "comment rows": comment._dump_comments_root,
        "suggestions": suggestions._suggestions_dump_root,
        "notifications": notifications._dump_root,
    }


@pytest.mark.parametrize("walker", ["post reading", "comment rows", "suggestions", "notifications"])
def test_a_walker_gets_the_tree_parse_ui_dump_built_in_one_dump(walker):
    phone = _Phone(_profile(STOCK))
    root = _walkers(BaseDeviceFacade(CloneAwareDeviceProxy(phone, STOCK)))[walker]()
    assert etree.tostring(root) == etree.tostring(parse_ui_dump(_profile(STOCK)))
    assert phone.dumps == 1


@pytest.mark.parametrize("walker", ["post reading", "comment rows", "suggestions", "notifications"])
def test_an_empty_hierarchy_is_no_tree(walker):
    """`<hierarchy/>` is a screen that could not be read, not a screen without the thing looked
    for: a walker gets None, as for a failed dump (it got an empty tree)."""
    phone = _Phone(EMPTY)
    assert _walkers(BaseDeviceFacade(phone))[walker]() is None


def test_the_comment_reader_asks_nothing_more_of_a_screen_it_cannot_read(monkeypatch):
    from taktik.core.social_media.instagram.workflows.common import comment_reading

    litho_asked = []
    monkeypatch.setattr(comment_reading, "run_adb_shell_process",
                        lambda *a, **k: litho_asked.append(a))
    facade = BaseDeviceFacade(_Phone(EMPTY))
    assert comment_reading.read_visible_comments(facade, device_id="serial") == []
    assert litho_asked == []
