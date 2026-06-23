"""Unit tests for the notifications XML-dump parsers (pure, from inline XML).

Covers the two real-device quirks confirmed on IG 410 dumps: activity-feed rows
carry a BARE resource-id while follow-request rows are fully-qualified — a bare
substring must match both.
"""

from lxml import etree

from taktik.core.social_media.instagram.workflows.management.notifications.dump_parsing import (
    find_inline_like_target,
    find_more_targets,
    find_row_reply_target,
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

# Follow-requests sub-screen, WITH containers (usernames + buttons carry bounds on
# the same horizontal band).
REQUESTS_XML = """<hierarchy>
  <node resource-id="com.instagram.android:id/follow_list_container">
    <node resource-id="com.instagram.android:id/follow_list_username" text="samir.akarioh" bounds="[200,455][500,520]" />
    <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,442][769,530]" />
    <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,442][1036,530]" />
  </node>
  <node resource-id="com.instagram.android:id/follow_list_container">
    <node resource-id="com.instagram.android:id/follow_list_username" text="dj_syl_" bounds="[200,658][500,720]" />
    <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,645][769,733]" />
    <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,645][1036,733]" />
  </node>
</hierarchy>"""

# Same rows but FLATTENED (no containers) — simulates a compressed live dump where
# the layout containers are collapsed. The parser must still pair by proximity.
REQUESTS_XML_FLAT = """<hierarchy>
  <node resource-id="com.instagram.android:id/follow_list_username" text="samir.akarioh" bounds="[200,455][500,520]" />
  <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,442][769,530]" />
  <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,442][1036,530]" />
  <node resource-id="com.instagram.android:id/follow_list_username" text="dj_syl_" bounds="[200,658][500,720]" />
  <node resource-id="com.instagram.android:id/row_requested_user_accept_secondary" bounds="[523,645][769,733]" />
  <node resource-id="com.instagram.android:id/row_requested_user_ignore" bounds="[780,645][1036,733]" />
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
        "follow_list_username",
        "row_requested_user_accept_secondary",
        "row_requested_user_ignore",
    )
    assert [r["username"] for r in rows] == ["samir.akarioh", "dj_syl_"]
    # Accept center of row 1: x=(523+769)/2=646, y=(442+530)/2=486
    assert rows[0]["accept"] == (646, 486)
    assert rows[0]["ignore"] == (908, 486)
    assert rows[1]["accept"] == (646, 689)


def test_parse_request_rows_container_independent():
    # A compressed dump drops the containers; pairing by vertical proximity must
    # still resolve each username to the Confirm/Delete button on its row.
    rows = parse_request_rows(
        _root(REQUESTS_XML_FLAT),
        "follow_list_username",
        "row_requested_user_accept_secondary",
        "row_requested_user_ignore",
    )
    assert [r["username"] for r in rows] == ["samir.akarioh", "dj_syl_"]
    assert rows[0]["accept"] == (646, 486)
    assert rows[1]["accept"] == (646, 689)


def test_parse_request_rows_empty_when_no_requests():
    rows = parse_request_rows(_root(FEED_XML), "follow_list_username",
                              "row_requested_user_accept_secondary",
                              "row_requested_user_ignore")
    assert rows == []


# Comment / mention rows expose a CLICKABLE inline "Like button" (content-desc, empty
# resource-id) on the left of the row. The already-liked row shows "Unlike button".
LIKE_XML = """<hierarchy>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,400][1080,560]">
    <node content-desc="Like button" bounds="[40,440][130,520]" />
    <node text="alice a commenté : top !" bounds="[150,440][1000,520]" />
  </node>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,560][1080,720]">
    <node content-desc="Unlike button" bounds="[40,600][130,680]" />
    <node text="bob a commenté : déjà aimé" bounds="[150,600][1000,680]" />
  </node>
</hierarchy>"""


def test_find_inline_like_returns_button_center_for_username():
    point = find_inline_like_target(_root(LIKE_XML), "activity_feed_newsfeed_story_row",
                                    ["Like button"], "alice")
    assert point == (85, 480)  # center of [40,440][130,520]


def test_find_inline_like_skips_already_liked_unlike_button():
    # "Unlike button" must NOT match "Like button" (exact content-desc), so liking
    # bob's already-liked row finds no fresh Like button -> None.
    point = find_inline_like_target(_root(LIKE_XML), "activity_feed_newsfeed_story_row",
                                    ["Like button"], "bob")
    assert point is None


def test_find_inline_like_none_when_username_absent():
    point = find_inline_like_target(_root(LIKE_XML), "activity_feed_newsfeed_story_row",
                                    ["Like button"], "carol")
    assert point is None


# Comment / mention rows carry a "Reply" / "Répondre" Button (text node) on the row.
REPLY_XML = """<hierarchy>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,400][1080,560]">
    <node text="alice a mentionné votre nom dans un commentaire" bounds="[150,420][1000,500]" />
    <node text="Bouton J'aime" bounds="[40,510][130,555]" />
    <node text="Répondre" bounds="[150,510][320,555]" />
  </node>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,560][1080,720]">
    <node text="bob a aimé votre photo" bounds="[150,580][1000,660]" />
  </node>
</hierarchy>"""


def test_find_row_reply_returns_button_center_for_username():
    point = find_row_reply_target(_root(REPLY_XML), "activity_feed_newsfeed_story_row",
                                  ["Répondre", "Reply"], "alice")
    assert point == (235, 532)  # center of [150,510][320,555]


def test_find_row_reply_none_when_row_has_no_reply():
    # bob's row (a like-only notification) has no Reply button -> None.
    point = find_row_reply_target(_root(REPLY_XML), "activity_feed_newsfeed_story_row",
                                  ["Répondre", "Reply"], "bob")
    assert point is None


# A truncated comment/mention row: text ends with "… more <time>"; the expander has no
# node, so the tap point is estimated from the text node bounds (last line, near right).
MORE_XML = """<hierarchy>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,834][1080,1132]">
    <node text="alice mentioned you: blah blah blah… more 1w" bounds="[253,857][893,1053]" />
  </node>
  <node resource-id="activity_feed_newsfeed_story_row" bounds="[0,1132][1080,1300]">
    <node text="bob a aimé votre photo. 4 j" bounds="[253,1160][893,1230]" />
  </node>
</hierarchy>"""


def test_find_more_targets_estimates_point_on_last_line():
    targets = find_more_targets(_root(MORE_XML), "activity_feed_newsfeed_story_row")
    assert len(targets) == 1  # only the truncated row
    x, y = targets[0]["point"]
    # ~18% of width (640) in from the right edge (893); ~12% of height (196) up from bottom (1053)
    assert (x, y) == (int(893 - 0.18 * 640), int(1053 - 0.12 * 196))
    assert 253 < x < 893 and 857 < y < 1053  # inside the text node bounds, last line, right side


def test_find_more_targets_skips_untruncated():
    xml = MORE_XML.replace("blah blah blah… more 1w", "short comment 1w")
    assert find_more_targets(_root(xml), "activity_feed_newsfeed_story_row") == []
