"""Instagram supplies live post-action bounds to the shared gesture start guard."""

from types import SimpleNamespace

from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import BaseScrollMixin


class _Log:
    def debug(self, *_args, **_kwargs):
        pass


class _Raw:
    def __init__(self, xml):
        self.xml = xml
        self.dumps = 0

    def dump_hierarchy(self):
        self.dumps += 1
        return self.xml


def _host(xml):
    host = object.__new__(BaseScrollMixin)
    host.device = SimpleNamespace(_device=_Raw(xml))
    host.logger = _Log()
    return host


def test_reads_named_and_anonymous_action_row_bounds():
    xml = """<hierarchy>
      <node resource-id="com.instagram.android:id/row_feed_photo_profile_name"
            bounds="[40,120][300,180]" />
      <node resource-id="com.instagram.android:id/row_feed_view_group_buttons"
            bounds="[0,1750][1080,1880]">
        <node resource-id="com.instagram.android:id/row_feed_button_like"
              clickable="true" bounds="[20,1760][130,1870]" />
        <node class="android.widget.Button" clickable="true" bounds="[130,1760][190,1870]" />
        <node resource-id="com.instagram.android:id/row_feed_button_comment"
              clickable="true" bounds="[190,1760][300,1870]" />
        <node resource-id="com.instagram.android:id/row_feed_button_share"
              clickable="true" bounds="[300,1760][420,1870]" />
        <node resource-id="com.instagram.android:id/row_feed_button_save"
              clickable="true" bounds="[940,1760][1060,1870]" />
      </node>
    </hierarchy>"""
    host = _host(xml)

    geometry = host._read_post_action_geometry()

    assert geometry["available"] is True
    assert geometry["post_visible"] is True
    assert geometry["roles"]["share"] == [(300, 1760, 420, 1870)]
    assert (130, 1760, 190, 1870) in geometry["roles"]["button"]
    assert host._gesture_start_exclusion_bounds() == geometry["bounds"]


def test_non_post_screen_has_no_exclusions():
    host = _host('<hierarchy><node resource-id="com.instagram.android:id/tab_bar" /></hierarchy>')

    assert host._gesture_start_exclusion_bounds() == []


def test_dump_failure_requests_ratio_fallback():
    host = _host("not xml")

    assert host._gesture_start_exclusion_bounds() is None
    assert host._gesture_fallback_safe_x_band() == (0.46, 0.70)


def test_existing_hierarchy_root_is_reused_then_invalidated():
    xml = """<hierarchy><node resource-id="com.instagram.android:id/row_feed_button_share"
      clickable="true" bounds="[300,1760][420,1870]" /></hierarchy>"""
    host = _host(xml)
    root = etree.fromstring(xml.encode("utf-8"))

    host._remember_post_action_geometry(root)
    bounds = host._gesture_start_exclusion_bounds()

    assert bounds == [(300, 1760, 420, 1870)]
    assert host.device._device.dumps == 0
    assert host._post_action_geometry_cache is None
