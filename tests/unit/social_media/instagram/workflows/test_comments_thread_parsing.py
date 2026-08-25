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
    <node class="android.widget.ImageView" bounds="[24,203][78,257]" content-desc="Go to commenter42's profile"/>
    <node class="android.view.ViewGroup" bounds="[84,185][492,302]" content-desc="">
      <node class="android.view.ViewGroup" bounds="[84,197][492,255]" content-desc="commenter42 ">
        <node class="android.widget.Button" bounds="[98,197][189,222]" content-desc="" text="commenter42"/>
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
    <node class="android.view.ViewGroup" bounds="[84,559][492,641]" content-desc="commenter77 ">
      <node class="android.widget.Button" bounds="[98,559][189,584]" content-desc="" text="commenter77"/>
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
        "commenter42": (492, 185, 576, 275),
        "taktik_r2d2": (492, 334, 576, 424),
        "commenter77": (492, 547, 576, 637),
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
    assert find_comment_like_target(_root(), "@commenter77", EN_LIKE, EN_UNLIKE) is not None


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
    assert find_comment_reply_target(_root(), "commenter42", REPLY_LABELS) == (98, 255, 170, 302)
    assert find_comment_reply_target(_root(), "taktik_r2d2", REPLY_LABELS) == (145, 500, 217, 547)
    assert find_comment_reply_target(_root(), "commenter77", REPLY_LABELS) == (98, 641, 170, 670)


def test_a_row_whose_reply_button_is_missing_yields_nothing():
    stripped = REAL_THREAD.replace(
        '<node class="android.widget.Button" bounds="[98,255][170,302]" content-desc="Reply" text="Reply"/>', "",
    )
    assert find_comment_reply_target(_root(stripped), "commenter42", REPLY_LABELS) is None


def test_the_reply_label_is_matched_case_insensitively_in_either_attribute():
    french = REAL_THREAD.replace('content-desc="Reply" text="Reply"', 'content-desc="Répondre" text=""')
    assert find_comment_reply_target(_root(french), "commenter42", REPLY_LABELS) is not None


def test_an_unknown_commenter_has_no_reply_target():
    assert find_comment_reply_target(_root(), "nobody_here", REPLY_LABELS) is None


def test_no_labels_means_no_blind_tap():
    assert find_comment_reply_target(_root(), "commenter42", []) is None


# ── IG 442: the same thread, rendered in Compose ────────────────────────────────────────
#
# Structure copied from a real 442 dump (2026-08-26), handles replaced. Three things changed
# and each one broke the pairing:
#   - the username moved from a Button with an EMPTY content-desc to a TextView that REPEATS
#     its text in content-desc, padded with a no-break space (written &#160; here so the file
#     carries no invisible character);
#   - "Reply", "See translation", the timestamp and the body repeat themselves the same way,
#     so "same text and desc" alone does not identify a username -- the TextView class does;
#   - a @mention inside a body is a Button with an empty content-desc, i.e. it looks exactly
#     like a LEGACY username label and would otherwise be read as a comment row of its own.
COMPOSE_THREAD = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,1037][1080,1280]" content-desc="">
    <node class="android.widget.ImageView" bounds="[42,1068][137,1163]" content-desc="View commenter42's story"/>
    <node class="android.view.ViewGroup" bounds="[148,1058][933,1199]" content-desc="">
      <node class="android.widget.TextView" bounds="[172,1058][423,1099]" text="commenter42" content-desc="commenter42&#160; "/>
      <node class="android.view.ViewGroup" bounds="[426,1058][472,1099]" text="6h" content-desc="6h"/>
      <node class="android.view.ViewGroup" bounds="[172,1110][933,1199]"
            text="commenter42 said what a place" content-desc="commenter42 said what a place"/>
    </node>
    <node class="android.view.View" bounds="[172,1199][363,1280]" text="Reply" content-desc="Reply"/>
    <node class="android.view.View" bounds="[363,1199][666,1280]" text="See translation" content-desc="See translation"/>
    <node class="android.widget.Button" bounds="[933,1037][1080,1195]" content-desc="Tap to like comment">
      <node class="android.widget.ImageView" bounds="[933,1037][1080,1153]" content-desc="Like"/>
    </node>
  </node>
  <node class="android.view.ViewGroup" bounds="[0,1337][1080,1540]" content-desc="">
    <node class="android.widget.ImageView" bounds="[148,1364][222,1438]" content-desc="Go to taktik_r2d2's profile"/>
    <node class="android.view.ViewGroup" bounds="[229,1358][933,1459]" content-desc="">
      <node class="android.widget.TextView" bounds="[253,1358][462,1401]" text="taktik_r2d2" content-desc="taktik_r2d2&#160; "/>
      <node class="android.view.ViewGroup" bounds="[465,1358][511,1401]" text="5h" content-desc="5h"/>
      <node class="android.view.ViewGroup" bounds="[253,1412][619,1459]"
            text="taktik_r2d2 said @commenter42 right!?" content-desc="taktik_r2d2 said @commenter42 right!?">
        <node class="android.widget.Button" bounds="[253,1412][499,1459]" text="@commenter42" content-desc=""/>
      </node>
    </node>
    <node class="android.view.View" bounds="[253,1459][444,1540]" text="Reply" content-desc="Reply"/>
    <node class="android.widget.Button" bounds="[933,1337][1080,1495]"
          content-desc="45 likes. Double tap to like a comment and press and hold to see all likes">
      <node class="android.widget.ImageView" bounds="[933,1337][1080,1453]" content-desc="Like"/>
      <node class="android.view.View" bounds="[987,1453][1025,1491]" text="45"/>
    </node>
  </node>
</hierarchy>
"""


def _compose_root():
    return etree.fromstring(COMPOSE_THREAD.encode())


def test_compose_usernames_are_found_despite_the_repeated_content_desc():
    root = _compose_root()
    assert find_comment_reply_target(root, "commenter42", ["reply"]) is not None
    assert find_comment_reply_target(root, "taktik_r2d2", ["reply"]) is not None


def test_compose_reply_lands_under_its_own_comment():
    root = _compose_root()
    assert find_comment_reply_target(root, "commenter42", ["reply"]) == (172, 1199, 363, 1280)
    assert find_comment_reply_target(root, "taktik_r2d2", ["reply"]) == (253, 1459, 444, 1540)


def test_a_mention_inside_a_body_is_not_read_as_its_own_comment_row():
    # The @commenter42 mention sits INSIDE taktik_r2d2's body, between that username and its
    # Reply. Counting it as a row would cut the row short and lose the Reply underneath it.
    root = _compose_root()
    assert find_comment_reply_target(root, "taktik_r2d2", ["reply"]) == (253, 1459, 444, 1540)


def test_compose_like_control_is_paired_to_its_row():
    root = _compose_root()
    target = find_comment_like_target(root, "commenter42", EN_LIKE, EN_UNLIKE)
    assert target is not None
    assert target["bounds"] == (933, 1037, 1080, 1195)
    assert target["already_liked"] is False


def test_a_comment_that_already_has_likes_is_left_alone_for_now():
    # KNOWN GAP, deliberate. On 442 a comment that already carries likes describes its heart as
    # "... to like A comment ...", which none of our labels match, so nothing is returned and the
    # caller does nothing. Broadening the label is NOT safe until the ALREADY-LIKED wording has
    # been observed on a device: if that wording keeps the same instruction sentence, a broader
    # match would tap a liked comment and UNLIKE it while reporting a like.
    root = _compose_root()
    assert find_comment_like_target(root, "taktik_r2d2", EN_LIKE, EN_UNLIKE) is None
