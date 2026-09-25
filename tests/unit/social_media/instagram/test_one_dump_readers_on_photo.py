"""Instagram's one-dump readers read a screen photo (steps 3 L5-L6 of the one-photo spec).

`batch_xpath_check` (screen signals, profile flags) and the profile readers asked their selectors
of plain lxml on `parse_ui_dump`: the right tree, but not the path `d.xpath()` takes behind the
`CloneAwareDeviceProxy` every Instagram bridge mounts. An id equality missed a clone's prefix and a
Compose screen's bare id, and a uiautomator2 shorthand was rejected. They now ask a photo, which
answers as `d.xpath()` does through the proxy, still on one dump. The readers that walk the tree
get the photo's tree: the same nodes as before, taken through the facade.

Dumps are invented, shaped on the real profile header (ids and nesting), texts made up.
"""

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


def _profile(package: str) -> str:
    """A professional profile's header, its ids under `package` (a clone renames the prefix)."""
    p = f"{package}:id/"

    def node(rid, cls="android.widget.TextView", text="", children="", bounds="[0,0][10,10]"):
        return (f'<node resource-id="{p + rid if rid else ""}" class="{cls}" package="{package}" '
                f'text="{text}" content-desc="" bounds="{bounds}">{children}</node>')

    header = node("profile_header_container", "android.widget.LinearLayout", children=(
        node("avatar_on_profile_header_view", "android.widget.Button", bounds="[40,300][240,500]",
             children=node("profilePic", "android.widget.ImageView", bounds="[50,310][230,490]"))
        + node("profile_header_full_name_above_vanity", text="Demo Studio")
        + node("profile_header_business_category", text="Artist")
        + node("profile_user_info_compose_view", "com.facebook.compose.view.MetaComposeView", children=(
            node("", "android.view.View", children=node("", text="Paints walls, answers mail")))
        )
        + node("banner_row", "android.widget.LinearLayout", children=node(
            "profile_header_banner_item_layout", "android.widget.LinearLayout",
            children=node("profile_header_banner_item_title", text="demo.studio")))
    ))
    bar = node("action_bar_username_container", "android.widget.LinearLayout",
               children=node("action_bar_title", text="demo.studio"))
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{bar}{header}</hierarchy>'


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
    dump = ('<hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" resource-id="{CLONE}:id/profile_header_container" />'
            '<node class="android.view.View" resource-id="activity_feed_list" /></hierarchy>')
    facade, phone = _facade(dump)
    answers = facade.batch_xpath_check({
        "clone": [f'//*[@resource-id="{STOCK}:id/profile_header_container"]'],
        "bare": [f'//*[@resource-id="{STOCK}:id/activity_feed_list"]'],
        "absent": [f'//*[@resource-id="{STOCK}:id/row_feed_button_like"]'],
    })
    assert answers == {"clone": True, "bare": True, "absent": False}
    assert phone.dumps == 1


def test_the_batch_check_reads_shorthands_and_skips_a_rejected_selector():
    dump = f'<hierarchy rotation="0"><node class="android.widget.TextView" resource-id="{STOCK}:id/title" /></hierarchy>'
    facade, _phone = _facade(dump)
    assert facade.batch_xpath_check({"title": ["//*[", f"@{STOCK}:id/title"]}) == {"title": True}


@pytest.mark.parametrize("xml", ['<hierarchy rotation="0" />', "", "<not xml"])
def test_an_unreadable_screen_answers_false_for_every_name(xml):
    facade, phone = _facade(xml)
    assert facade.batch_xpath_check({"a": ["//*"], "b": ["//node"]}) == {"a": False, "b": False}
    assert phone.dumps == 1


def test_a_dump_already_held_is_checked_without_a_device_call():
    facade, phone = _facade("")
    held = '<hierarchy rotation="0"><node class="android.view.View" resource-id="activity_feed_list" /></hierarchy>'
    assert facade.xpath_exists_in_xml(held, f'//*[@resource-id="{STOCK}:id/activity_feed_list"]')
    assert not facade.xpath_exists_in_xml(held, '//*[@text="absent"]')
    assert not facade.xpath_exists_in_xml("", "//*")
    assert phone.dumps == 0


# --------------------------------------------------------------------------- profile readers

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
    assert answers["text"] == {"username": "demo.studio", "full_name": "Demo Studio",
                               "biography": "Paints walls, answers mail"}
    assert answers["enriched"]["business_category"] == "Artist"
    assert answers["enriched"]["linked_accounts"] == [{"name": "demo.studio", "platform": "unknown"}]
    assert answers["avatar"] is True
    assert phone.dumps == 4  # one photo per reader call


def test_a_clone_reads_like_the_stock_app():
    """Behind the proxy, a clone's header answers as the stock one: every equality of these
    readers used to miss the clone's prefix."""
    assert _read_all(CLONE)[0] == _read_all(STOCK)[0]


def test_the_bounded_bio_read_is_one_dump_through_the_timeout():
    facade, phone = _facade(_profile(STOCK).replace("Paints walls, answers mail", "A long bio cut short…"))
    calls = []
    real = facade.get_xml_dump

    def bounded(timeout_seconds=None):
        calls.append(timeout_seconds)
        return real()

    facade.get_xml_dump = bounded
    assert _Reader(facade)._truncated_bio_region() == (0, 0, 10, 10)
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
    phone = _Phone('<hierarchy rotation="0" />')
    assert _walkers(BaseDeviceFacade(phone))[walker]() is None


def test_the_comment_reader_asks_nothing_more_of_a_screen_it_cannot_read(monkeypatch):
    from taktik.core.social_media.instagram.workflows.common import comment_reading

    litho_asked = []
    monkeypatch.setattr(comment_reading, "run_adb_shell_process",
                        lambda *a, **k: litho_asked.append(a))
    facade = BaseDeviceFacade(_Phone('<hierarchy rotation="0" />'))
    assert comment_reading.read_visible_comments(facade, device_id="serial") == []
    assert litho_asked == []
