"""The notifications dump parsers, on real activity screens.

The screens are real captures, anonymized, read with the production catalogue
(``NOTIFICATION_SELECTORS``): Instagram 410 in French (Pixel 4a, 2026-09-28: new followers with
their « Suivre en retour » or « Envoyer un message » button, two mentions with « Bouton J’aime »
and « Répondre », two rows cut by « … suite ») and in English (Pixel 3a: « Follow back »,
« Like button », « Reply », « … more »). Activity rows carry a BARE resource-id, which a bare
substring must match.

Still written by hand: the follow-requests screen (``follow_list_username`` and its Confirm /
Delete buttons). The Pixel 4a account is public, and the Pixel 3a shows the « Follow requests »
entry but no capture opened it: capture it on a private account with a pending request.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors import NOTIFICATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.management.notifications.classifier import (
    classify_row,
    row_has_action,
)
from taktik.core.social_media.instagram.workflows.management.notifications.dump_parsing import (
    find_inline_follow_back_target,
    find_inline_like_target,
    find_row_reply_target,
    find_truncated_targets,
    parse_feed_rows,
    parse_request_rows,
)
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FRENCH = "ig410_fr_notifications_rows.xml"
ENGLISH = "ig410_en_notifications.xml"
ROW = NOTIFICATION_SELECTORS.notification_row_resource_id


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _root(name):
    return parse_ui_dump(_capture(name))


@pytest.fixture
def language():
    yield set_active_locale
    set_active_locale(None)


def test_parse_feed_rows_matches_bare_resource_id(language):
    language("fr")
    assert f'resource-id="{ROW}"' in _capture(FRENCH)  # bare, no package prefix
    rows = parse_feed_rows(_root(FRENCH), ROW, NOTIFICATION_SELECTORS.classifier_fragments)
    assert [(row["type"], row["username"], row["time"]) for row in rows] == [
        ("comment_mention", "user_1", "4 j"),
        ("new_follower", "user_3", "5 j"),
        ("new_follower", "user_4", "5 j"),
        ("other", "", "5 j"),
        ("new_follower", "name_23", "5 j"),
        ("comment_mention", "user_6", "5 j"),
        ("comment_like", "user_6", "5 j"),
        ("new_follower", "user_7", "5 j"),
        ("new_follower", "user_8", "5 j"),
        ("other", "", "5 j"),
    ]
    # « Répondre », « Suivre en retour » or « Envoyer un message » on the row.
    assert [row["has_action"] for row in rows] == [True, True, True, False, True, True, False,
                                                   True, True, False]


def test_a_follow_request_row_is_classified_with_its_action(language):
    """The text of a request row, as the dump joins it (no capture holds one on screen)."""
    language("fr")
    text = "bob a demandé à vous suivre. 3 j · Confirmer"
    assert classify_row(text, NOTIFICATION_SELECTORS.classifier_fragments) == ("follow_request", "bob")
    assert row_has_action(text)


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


def _request_rows(xml):
    return parse_request_rows(
        parse_ui_dump(xml),
        NOTIFICATION_SELECTORS.follow_request_username_resource_id,
        NOTIFICATION_SELECTORS.follow_request_accept_resource_id,
        NOTIFICATION_SELECTORS.follow_request_ignore_resource_id,
    )


def test_parse_request_rows_username_and_tap_points():
    rows = _request_rows(REQUESTS_XML)
    assert [r["username"] for r in rows] == ["samir.akarioh", "dj_syl_"]
    # Accept center of row 1: x=(523+769)/2=646, y=(442+530)/2=486
    assert rows[0]["accept"] == (646, 486)
    assert rows[0]["ignore"] == (908, 486)
    assert rows[1]["accept"] == (646, 689)


def test_parse_request_rows_container_independent():
    # A compressed dump drops the containers; pairing by vertical proximity must
    # still resolve each username to the Confirm/Delete button on its row.
    rows = _request_rows(REQUESTS_XML_FLAT)
    assert [r["username"] for r in rows] == ["samir.akarioh", "dj_syl_"]
    assert rows[0]["accept"] == (646, 486)
    assert rows[1]["accept"] == (646, 689)


@pytest.mark.parametrize("name", [FRENCH, ENGLISH])
def test_parse_request_rows_empty_when_no_requests(name):
    assert _request_rows(_capture(name)) == []


# Comment / mention rows expose a CLICKABLE inline like control (content-desc « Bouton J’aime »
# in French, with the typographic apostrophe the catalogue writes as ASCII; « Like button » in
# English) on the left of the row.
LIKES = {
    # user_1's mention: « Bouton J’aime » at [204,290][311,390]; user_6's at [204,1366][311,1468].
    "fr": (FRENCH, {"user_1": (257, 340), "user_6": (257, 1417)}),
    # user_3's mention: « Like button » at [204,788][289,896].
    "en": (ENGLISH, {"user_3": (246, 842)}),
}


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_find_inline_like_returns_button_center_for_username(language, lang):
    language(lang)
    name, expected = LIKES[lang]
    for username, point in expected.items():
        assert find_inline_like_target(_root(name), ROW, NOTIFICATION_SELECTORS.inline_like_button,
                                       username) == point


def test_find_inline_like_matches_the_whole_label_only(language):
    """An exact match, never a part of the label: the already-liked state reads as another label
    that contains this one, and a like must never be undone. A part of the real label finds
    nothing on the real row."""
    language("fr")
    assert find_inline_like_target(_root(FRENCH), ROW, ["J’aime"], "user_1") is None
    assert find_inline_like_target(_root(FRENCH), ROW, ["Bouton"], "user_1") is None


@pytest.mark.parametrize("lang, username", [("fr", "user_3"), ("en", "user_1")])
def test_find_inline_like_none_on_a_row_without_one(language, lang, username):
    """A new-follower row has no like control."""
    language(lang)
    name = LIKES[lang][0]
    assert find_inline_like_target(_root(name), ROW, NOTIFICATION_SELECTORS.inline_like_button,
                                   username) is None


def test_find_inline_like_none_when_username_absent(language):
    language("fr")
    assert find_inline_like_target(_root(FRENCH), ROW, NOTIFICATION_SELECTORS.inline_like_button,
                                   "carol") is None


# New-follower rows carry an inline igds_button whose CONTAINER is empty — the label lives on a
# child TextView. A follower already followed back shows « Envoyer un message » / « Message »
# there, and must never match.
FOLLOW_BACKS = {
    # user_7: « Suivre en retour » at [699,1758][992,1804]; user_8: « Envoyer un message ».
    "fr": (FRENCH, "user_7", (845, 1781), "user_8"),
    # user_1: « Follow back » at [779,560][992,606]; user_8: « Message ».
    "en": (ENGLISH, "user_1", (885, 583), "user_8"),
}


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_find_inline_follow_back_returns_label_center_for_username(language, lang):
    language(lang)
    name, username, point, _followed = FOLLOW_BACKS[lang]
    assert find_inline_follow_back_target(_root(name), ROW, NOTIFICATION_SELECTORS.inline_follow_back_button,
                                          username) == point


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_find_inline_follow_back_skips_already_followed_row(language, lang):
    language(lang)
    name, _username, _point, followed = FOLLOW_BACKS[lang]
    assert find_inline_follow_back_target(_root(name), ROW, NOTIFICATION_SELECTORS.inline_follow_back_button,
                                          followed) is None


def test_find_inline_follow_back_none_when_username_absent(language):
    language("fr")
    assert find_inline_follow_back_target(_root(FRENCH), ROW, NOTIFICATION_SELECTORS.inline_follow_back_button,
                                          "carol") is None


# Comment / mention rows carry a « Répondre » / « Reply » TextView on the row.
REPLIES = {
    # user_1: « Répondre » at [311,290][463,390].
    "fr": (FRENCH, "user_1", (387, 340)),
    # user_3: « Reply » at [289,788][421,896].
    "en": (ENGLISH, "user_3", (355, 842)),
}


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_find_row_reply_returns_button_center_for_username(language, lang):
    language(lang)
    name, username, point = REPLIES[lang]
    assert find_row_reply_target(_root(name), ROW, NOTIFICATION_SELECTORS.reply_label, username) == point


def test_find_row_reply_none_when_row_has_no_reply(language):
    # user_3's row (a new follower) has no Reply button -> None.
    language("fr")
    assert find_row_reply_target(_root(FRENCH), ROW, NOTIFICATION_SELECTORS.reply_label, "user_3") is None


# Truncated rows (« … suite » / « … more ») -> the OCR region = the text node's REAL bounds.
def test_find_truncated_targets_returns_text_node_region():
    targets = find_truncated_targets(_root(FRENCH), ROW)
    # user_6's mention and user_6's liked comment, both cut; the other rows are whole.
    assert [target["region"] for target in targets] == [(253, 1199, 893, 1395), (253, 1485, 893, 1681)]
    assert all("… suite" in target["key"] for target in targets)
    english = find_truncated_targets(_root(ENGLISH), ROW)
    assert [target["region"] for target in english] == [(253, 1143, 893, 1339)]
    assert "… more" in english[0]["key"]


def test_find_truncated_targets_skips_untruncated():
    """The top of the French screen: new followers and likes, nothing cut."""
    xml = _capture("ig410_fr_notifications_top.xml")
    assert "… suite" not in xml
    assert find_truncated_targets(parse_ui_dump(xml), ROW) == []
