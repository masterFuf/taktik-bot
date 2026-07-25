"""Pairing a comment's heart to the right comment.

A comment row carries no resource-id, so the control is paired to its author by geometry.
The fixture below is copied verbatim from a real device dump (2026-02-08) — three comments,
two of them already carrying likes, one with none — because inventing a hierarchy would only
test the invention.
"""

from lxml import etree

from taktik.core.social_media.instagram.workflows.common.comments_thread import (
    center,
    find_comment_like_target,
    find_comment_reply_target,
    parse_bounds,
)

EN_LIKE = ["to like comment"]
EN_UNLIKE = ["to unlike comment"]
FR_LIKE = ["aimer le commentaire"]
FR_UNLIKE = ["ne plus aimer le commentaire"]

# Real dump, trimmed to the comment rows. Note the post card's own counter buttons at the
# bottom: they sit under the sheet and must never be mistaken for a row.
REAL_THREAD = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,185][576,302]" content-desc="">
    <node class="android.widget.ImageView" bounds="[24,203][78,257]" content-desc="Go to dianeou38's profile"/>
    <node class="android.view.ViewGroup" bounds="[84,185][492,302]" content-desc="">
      <node class="android.view.ViewGroup" bounds="[84,197][492,255]" content-desc="dianeou38 ">
        <node class="android.widget.Button" bounds="[98,197][189,222]" content-desc="" text="dianeou38"/>
      </node>
      <node class="android.widget.Button" bounds="[98,255][170,302]" content-desc="Reply" text="Reply"/>
    </node>
    <node class="android.widget.Button" bounds="[492,185][576,275]"
          content-desc="1 likes. Double tap to like comment and press and hold to see all likes"/>
  </node>
  <node class="android.view.ViewGroup" bounds="[0,334][576,547]" content-desc="">
    <node class="android.widget.ImageView" bounds="[85,350][127,392]" content-desc="Go to taktik_r2d2's profile"/>
    <node class="android.view.ViewGroup" bounds="[131,334][492,547]" content-desc="">
      <node class="android.view.ViewGroup" bounds="[131,346][492,500]" content-desc="taktik_r2d2 ">
        <node class="android.widget.Button" bounds="[145,346][243,371]" content-desc="" text="taktik_r2d2"/>
      </node>
      <node class="android.widget.Button" bounds="[145,500][217,547]" content-desc="Reply" text="Reply"/>
    </node>
    <node class="android.widget.Button" bounds="[492,334][576,424]" content-desc="Tap to like comment">
      <node class="android.widget.ImageView" bounds="[492,334][576,400]" content-desc="Like"/>
    </node>
  </node>
  <node class="android.view.ViewGroup" bounds="[0,547][576,670]" content-desc="">
    <node class="android.view.ViewGroup" bounds="[84,559][492,641]" content-desc="maryonlnd ">
      <node class="android.widget.Button" bounds="[98,559][189,584]" content-desc="" text="maryonlnd"/>
    </node>
    <node class="android.widget.Button" bounds="[98,641][170,670]" content-desc="Reply" text="Reply"/>
    <node class="android.widget.Button" bounds="[492,547][576,637]"
          content-desc="3 likes. Double tap to like comment and press and hold to see all likes"/>
  </node>
  <node class="android.widget.Button" bounds="[60,955][114,1024]" content-desc="" text="18.5K"/>
  <node class="android.widget.Button" bounds="[174,955][211,1024]" content-desc="" text="428"/>
</hierarchy>
"""


def _root(xml=REAL_THREAD):
    return etree.fromstring(xml.strip().encode("utf-8"))


# ── Bounds helpers ──────────────────────────────────────────────────────────

def test_bounds_are_parsed_and_centred():
    assert parse_bounds("[492,185][576,275]") == (492, 185, 576, 275)
    assert center((492, 185, 576, 275)) == (534, 230)


def test_unparseable_bounds_yield_none_rather_than_raising():
    assert parse_bounds("") is None
    assert parse_bounds("garbage") is None


# ── Pairing a control to the right author ───────────────────────────────────

def test_each_commenter_gets_its_own_heart():
    """Three rows, three distinct controls — no cross-matching between neighbours."""
    expected = {
        "dianeou38": (492, 185, 576, 275),
        "taktik_r2d2": (492, 334, 576, 424),
        "maryonlnd": (492, 547, 576, 637),
    }
    for username, bounds in expected.items():
        found = find_comment_like_target(_root(), username, EN_LIKE, EN_UNLIKE)
        assert found is not None, username
        assert found["bounds"] == bounds
        assert found["already_liked"] is False


def test_the_full_box_is_returned_so_the_tap_can_be_humanised():
    found = find_comment_like_target(_root(), "taktik_r2d2", EN_LIKE, EN_UNLIKE)
    left, top, right, bottom = found["bounds"]
    assert right > left and bottom > top


def test_an_unknown_commenter_is_reported_missing():
    assert find_comment_like_target(_root(), "nobody_here", EN_LIKE, EN_UNLIKE) is None


def test_an_empty_username_is_refused():
    assert find_comment_like_target(_root(), "", EN_LIKE, EN_UNLIKE) is None
    assert find_comment_like_target(_root(), "   ", EN_LIKE, EN_UNLIKE) is None


def test_the_at_sign_is_tolerated():
    assert find_comment_like_target(_root(), "@maryonlnd", EN_LIKE, EN_UNLIKE) is not None


# ── Never turning a like into an unlike ─────────────────────────────────────

def test_an_already_liked_comment_is_reported_as_such():
    liked = REAL_THREAD.replace(
        "Tap to like comment",
        "1 like. Double tap to unlike comment and press and hold to see all likes",
    )
    found = find_comment_like_target(_root(liked), "taktik_r2d2", EN_LIKE, EN_UNLIKE)
    assert found is not None
    assert found["already_liked"] is True


def test_french_liked_state_is_not_read_as_not_liked():
    """The French liked label CONTAINS the not-liked one ("ne plus aimer le commentaire"
    contains "aimer le commentaire"), so testing the positive token first would tap a liked
    comment and silently unlike it. The negative token must win."""
    french = REAL_THREAD.replace(
        "Tap to like comment",
        "Appuyez deux fois pour ne plus aimer le commentaire",
    )
    found = find_comment_like_target(_root(french), "taktik_r2d2", FR_LIKE, FR_UNLIKE)
    assert found is not None
    assert found["already_liked"] is True


def test_french_not_liked_state_is_actionable():
    french = REAL_THREAD.replace(
        "Tap to like comment", "Appuyez deux fois pour aimer le commentaire",
    )
    found = find_comment_like_target(_root(french), "taktik_r2d2", FR_LIKE, FR_UNLIKE)
    assert found["already_liked"] is False


def test_a_row_whose_control_matches_no_known_label_is_not_tapped():
    """Locale drift must not produce a blind tap on an unidentified control."""
    drifted = REAL_THREAD.replace("Tap to like comment", "Etwas ganz anderes")
    assert find_comment_like_target(_root(drifted), "taktik_r2d2", EN_LIKE, EN_UNLIKE) is None


def test_the_post_cards_counters_are_not_mistaken_for_a_row():
    """"18.5K" and "428" are Buttons with an empty content-desc, exactly like a username."""
    for fake in ("18.5K", "428"):
        assert find_comment_like_target(_root(), fake, EN_LIKE, EN_UNLIKE) is None


# ── Reply affordance ────────────────────────────────────────────────────────

REPLY_LABELS = ["reply", "répondre"]


def test_each_reply_button_belongs_to_its_own_comment():
    """Three rows, three Reply buttons a few dozen pixels apart. Reply sits BELOW its
    username (unlike the heart, which spans the row), so the pairing follows reading order
    — and it must not drift by one row: answering under the wrong comment is not
    recoverable."""
    assert find_comment_reply_target(_root(), "dianeou38", REPLY_LABELS) == (98, 255, 170, 302)
    assert find_comment_reply_target(_root(), "taktik_r2d2", REPLY_LABELS) == (145, 500, 217, 547)
    assert find_comment_reply_target(_root(), "maryonlnd", REPLY_LABELS) == (98, 641, 170, 670)


def test_a_row_whose_reply_button_is_missing_yields_nothing():
    stripped = REAL_THREAD.replace(
        '<node class="android.widget.Button" bounds="[98,255][170,302]" content-desc="Reply" text="Reply"/>', "",
    )
    assert find_comment_reply_target(_root(stripped), "dianeou38", REPLY_LABELS) is None


def test_the_reply_label_is_matched_case_insensitively_in_either_attribute():
    french = REAL_THREAD.replace('content-desc="Reply" text="Reply"', 'content-desc="Répondre" text=""')
    assert find_comment_reply_target(_root(french), "dianeou38", REPLY_LABELS) is not None


def test_an_unknown_commenter_has_no_reply_target():
    assert find_comment_reply_target(_root(), "nobody_here", REPLY_LABELS) is None


def test_no_labels_means_no_blind_tap():
    assert find_comment_reply_target(_root(), "dianeou38", []) is None
