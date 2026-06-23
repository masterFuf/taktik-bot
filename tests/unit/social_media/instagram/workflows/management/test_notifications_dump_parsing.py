"""Unit tests for the notifications XML-dump parsers (pure, from inline XML).

Covers the two real-device quirks confirmed on IG 410 dumps: activity-feed rows
carry a BARE resource-id while follow-request rows are fully-qualified — a bare
substring must match both.
"""

from lxml import etree

from taktik.core.social_media.instagram.workflows.management.notifications.dump_parsing import (
    parse_feed_rows,
    parse_request_rows,
)

FRAGMENTS = {
    "new_follower": ["a commencé à vous suivre", "started following you"],
    "follow_request": ["a demandé à vous suivre", "requested to follow you"],
}

# Feed rows: BARE resource-id (no package prefix), text split across descendants.
FEED_XML = """<hierarchy>
  <node resource-id="activity_feed_list">
    <node resource-id="activity_feed_newsfeed_story_row">
      <node text="alice" />
      <node text="a commencé à vous suivre. 2 j" />
    </node>
    <node resource-id="activity_feed_newsfeed_story_row">
      <node content-desc="bob a demandé à vous suivre. 3 j · Confirmer" />
    </node>
  </node>
</hierarchy>"""

# Follow-requests sub-screen: FULLY-QUALIFIED resource-ids, buttons carry bounds.
REQUESTS_XML = """<hierarchy>
  <node resource-id="com.instagram.android:id/follow_list_container">
    <node resource-id="com.instagram.android:id/follow_list_username" text="samir.akarioh" />
    <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,442][769,530]" />
    <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,442][1036,530]" />
  </node>
  <node resource-id="com.instagram.android:id/follow_list_container">
    <node resource-id="com.instagram.android:id/follow_list_username" text="dj_syl_" />
    <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,645][769,733]" />
    <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,645][1036,733]" />
  </node>
</hierarchy>"""


def _root(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


def test_parse_feed_rows_matches_bare_resource_id():
    rows = parse_feed_rows(_root(FEED_XML), "activity_feed_newsfeed_story_row", FRAGMENTS)
    assert len(rows) == 2
    assert rows[0]["type"] == "new_follower"
    assert rows[0]["username"] == "alice"
    assert rows[0]["time"] == "2 j"
    assert rows[1]["type"] == "follow_request"
    assert rows[1]["username"] == "bob"
    assert rows[1]["has_action"] is True  # "Confirmer"


def test_parse_request_rows_username_and_tap_points():
    rows = parse_request_rows(
        _root(REQUESTS_XML),
        "follow_list_container",
        "follow_list_username",
        "row_requested_user_accept_secondary",
        "row_requested_user_ignore",
    )
    assert [r["username"] for r in rows] == ["samir.akarioh", "dj_syl_"]
    # Accept center of row 1: x=(523+769)/2=646, y=(442+530)/2=486
    assert rows[0]["accept"] == (646, 486)
    assert rows[0]["ignore"] == (908, 486)
    assert rows[1]["accept"] == (646, 689)


def test_parse_request_rows_empty_when_no_container():
    rows = parse_request_rows(_root(FEED_XML), "follow_list_container",
                              "follow_list_username", "row_requested_user_accept_secondary",
                              "row_requested_user_ignore")
    assert rows == []
