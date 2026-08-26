"""Parsing of the account suggestions (feed carousel and discovery screen).

The dumps below are ANONYMISED extracts of a real capture
(Instagram v410.0.0.53.71): the structure, the
resource-ids and the button labels are the device ones, the account names
ont ete remplaces.

What is locked here:
- the carousel CTA is read with its bounds, being the entry point of the mode;
- a follow-back row is NEVER offered to the follow, since follow-back belongs
    to the notifications workflow;
- an already-followed or requested row is not tapped again;
- the section a row belongs to is resolved by vertical position;
- the call-to-action rows are not taken for suggestions.
  
"""

import pytest

from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import (
    FEED_SUGGESTIONS_SELECTORS,
)

from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
    classify_follow_state,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions_parsing import (
    followable_rows,
    is_discover_people_screen,
    parse_feed_suggestions_carousel,
    parse_section_headers,
    parse_suggestion_rows,
    read_screen_title,
)
from taktik.core.social_media.instagram.ui.selectors import (
    DISCOVER_PEOPLE_SELECTORS,
    FEED_SUGGESTIONS_SELECTORS,
    PROFILE_SELECTORS,
)


IG = "com.instagram.android:id"


FEED_CAROUSEL_DUMP = f"""<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node resource-id="{IG}/netego_carousel_container_view" bounds="[0,1150][1080,1967]">
    <node resource-id="{IG}/netego_carousel_header" bounds="[0,1150][1080,1260]">
      <node resource-id="{IG}/netego_carousel_title" text="Suggested for you" bounds="[39,1172][381,1222]"/>
      <node resource-id="{IG}/netego_carousel_cta" text="See all" bounds="[880,1172][1036,1222]"/>
    </node>
    <node resource-id="{IG}/netego_carousel_view" bounds="[0,1260][1080,1967]">
      <node resource-id="{IG}/suggested_entity_card_container" bounds="[39,1260][657,1967]">
        <node resource-id="{IG}/suggested_entity_card_name" text="Account One" bounds="[227,1734][469,1780]"/>
        <node resource-id="{IG}/suggested_entity_card_context" text="1 mutual" bounds="[325,1799][453,1838]"/>
        <node resource-id="{IG}/suggested_user_card_follow_button" text="Follow"
              content-desc="Follow Account One" bounds="[72,1887][624,1967]"/>
      </node>
      <node resource-id="{IG}/suggested_entity_card_container" bounds="[690,1260][1080,1967]">
        <node resource-id="{IG}/suggested_entity_card_name" text="Account Two" bounds="[834,1734][1080,1780]"/>
        <node resource-id="{IG}/suggested_user_card_follow_button" text="Follow"
              content-desc="Follow Account Two" bounds="[723,1887][1080,1967]"/>
      </node>
    </node>
  </node>
</hierarchy>
"""


def _row(top, name, button_text, context="1 mutual"):
    """A recommendation row as it is rendered, with the button inside the subtree."""
    bottom = top + 220
    return f"""
      <node resource-id="{IG}/recommended_user_row_content_identifier" bounds="[0,{top}][1080,{bottom}]">
        <node resource-id="{IG}/row_recommended_user_username" text="{name}"
              bounds="[231,{top + 52}][620,{top + 102}]"/>
        <node resource-id="{IG}/row_recommended_social_context" text="{context}"
              bounds="[297,{top + 119}][425,{top + 161}]"/>
        <node resource-id="{IG}/row_recommended_user_follow_button" text="{button_text}"
              content-desc="{button_text}" bounds="[653,{top + 66}][959,{top + 154}]"/>
        <node resource-id="{IG}/row_recommended_hide_icon_button" content-desc="Dismiss"
              bounds="[1003,{top + 93}][1036,{top + 126}]"/>
      </node>"""


DISCOVER_DUMP = f"""<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node resource-id="{IG}/action_bar_title" text="Discover people" bounds="[198,121][619,186]"/>
  <node resource-id="{IG}/recycler_view" bounds="[0,231][1080,2088]">
    <node resource-id="{IG}/contacts_button" bounds="[0,440][1080,638]">
      <node resource-id="{IG}/find_people_title" text="Connect contacts" bounds="[231,490][554,539]"/>
      <node resource-id="{IG}/find_people_action_button" text="Connect" bounds="[790,495][1036,583]"/>
    </node>
    <node resource-id="{IG}/row_header_textview" text="Suggested for you" bounds="[0,683][1080,815]"/>
    {_row(815, "Known Follower", "Follow back")}
    {_row(1035, "Fresh Account", "Follow")}
    {_row(1255, "Pending Account", "Requested")}
    <node resource-id="{IG}/row_header_textview" text="More suggestions" bounds="[0,1475][1080,1607]"/>
    {_row(1607, "Second Fresh", "Follow", context="Suggested for you")}
    {_row(1827, "Already Followed", "Following")}
  </node>
</hierarchy>
"""


def _root(xml):
    return etree.fromstring(xml.encode("utf-8"))


# --- feed carousel -----------------------------------------------------------

def test_carousel_exposes_its_cta_and_cards():
    carousel = parse_feed_suggestions_carousel(_root(FEED_CAROUSEL_DUMP),
                                               FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is True
    assert carousel["title"] == "Suggested for you"
    # The CTA is tapped on its real bounds, never on a hardcoded coordinate.
    assert carousel["cta_bounds"] == (880, 1172, 1036, 1222)
    assert [card["name"] for card in carousel["cards"]] == ["Account One", "Account Two"]
    assert all(card["follow_bounds"] for card in carousel["cards"])


def test_carousel_absent_from_a_plain_feed_dump():
    carousel = parse_feed_suggestions_carousel(
        _root(f"<hierarchy><node resource-id='{IG}/row_feed_button_like'/></hierarchy>"),
        FEED_SUGGESTIONS_SELECTORS,
    )
    assert carousel["present"] is False
    assert carousel["cta_bounds"] is None


# --- people discovery screen -------------------------------------------------

def test_discover_screen_is_recognised_structurally():
    assert is_discover_people_screen(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS) is True
    assert read_screen_title(_root(DISCOVER_DUMP)) == "Discover people"


def test_a_username_alone_is_not_the_discover_screen():
    """An isolated recommended-user row, in the tail of a followers list, must not be
    taken for the suggestions screen."""
    xml = f"<hierarchy><node resource-id='{IG}/row_recommended_user_username' text='X'/></hierarchy>"
    assert is_discover_people_screen(_root(xml), DISCOVER_PEOPLE_SELECTORS) is False


def test_rows_are_read_with_their_state_and_section():
    rows = parse_suggestion_rows(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS,
                                 PROFILE_SELECTORS, classify_follow_state)
    labels = [(row["label"], row["state"], row["section"]) for row in rows]
    assert labels == [
        ("Known Follower", "follow_back", "Suggested for you"),
        ("Fresh Account", "follow", "Suggested for you"),
        ("Pending Account", "requested", "Suggested for you"),
        ("Second Fresh", "follow", "More suggestions"),
        ("Already Followed", "following", "More suggestions"),
    ]


def test_connect_rows_are_not_suggestions():
    rows = parse_suggestion_rows(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS,
                                 PROFILE_SELECTORS, classify_follow_state)
    assert all("Connect" not in (row["label"] or "") for row in rows)


def test_only_plain_follow_rows_are_followable():
    """Business rule: no follow-back, no pending request, no already-followed."""
    rows = parse_suggestion_rows(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS,
                                 PROFILE_SELECTORS, classify_follow_state)
    targets = followable_rows(rows)
    assert [row["label"] for row in targets] == ["Fresh Account", "Second Fresh"]
    assert all(row["follow_bounds"] for row in targets)


def test_section_headers_are_ordered_top_down():
    headers = parse_section_headers(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS)
    assert [header["label"] for header in headers] == ["Suggested for you", "More suggestions"]


@pytest.mark.parametrize("root", [None])
def test_parsers_tolerate_a_missing_dump(root):
    assert parse_feed_suggestions_carousel(root, FEED_SUGGESTIONS_SELECTORS)["present"] is False
    assert is_discover_people_screen(root, DISCOVER_PEOPLE_SELECTORS) is False
    assert parse_suggestion_rows(root, DISCOVER_PEOPLE_SELECTORS, PROFILE_SELECTORS,
                                 classify_follow_state) == []


# --- libelles francais -------------------------------------------------------

def test_french_follow_labels_are_classified():
    """In one language the suggestions mode followed nobody: the app alternates between
    two verb families and the catalog carried only the first, so a button of the second
    matched NO label at all, the state stayed unset, and the row was skipped in
    silence.

    The apostrophe matters as much as the word: the app renders a TYPOGRAPHIC one while
    the catalogs are typed with the ASCII one."""
    from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

    set_active_locale('fr')
    try:
        assert classify_follow_state("Suivre", PROFILE_SELECTORS) == 'follow'
        assert classify_follow_state("S'abonner", PROFILE_SELECTORS) == 'follow'
        assert classify_follow_state("S\u2019abonner", PROFILE_SELECTORS) == 'follow'
        # The order still matters: the follow-back label contains the follow one.
        assert classify_follow_state("Suivre en retour", PROFILE_SELECTORS) == 'follow_back'
        assert classify_follow_state("S\u2019abonner en retour", PROFILE_SELECTORS) == 'follow_back'
        assert classify_follow_state("Abonn\u00e9", PROFILE_SELECTORS) == 'following'
    finally:
        set_active_locale(None)


def test_only_the_french_follow_rows_are_followable():
    """The same screen in the other language: only the followable rows are tapped."""
    from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

    following, follow_back, follow = "Abonné", "S’abonner en retour", "S’abonner"
    body = (_row(400, "Deja abonne", following) + _row(620, "Me suit", follow_back)
            + _row(840, "Inconnu", follow))
    xml = "<?xml version='1.0' encoding='UTF-8'?><hierarchy>" + body + "</hierarchy>"

    set_active_locale('fr')
    try:
        rows = parse_suggestion_rows(_root(xml), DISCOVER_PEOPLE_SELECTORS,
                                     PROFILE_SELECTORS, classify_follow_state)
        assert [row['state'] for row in rows] == ['following', 'follow_back', 'follow']
        assert [row['label'] for row in followable_rows(rows)] == ['Inconnu']
    finally:
        set_active_locale(None)


# ── IG 442: the carousel kept its shape and lost every resource-id ───────────────────────
#
# Structure from a real 442 capture (2026-08-26). `netego_carousel_*` is absent from the dump
# ENTIRELY -- header and CTA are two labelled ViewGroups on one row, and nothing else marks the
# block. Since that CTA is the only entry point to the people-discovery screen in the whole
# codebase, losing it made the surface unreachable rather than merely undetected.
COMPOSE_CAROUSEL = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,1560][1080,1700]" content-desc="">
    <node class="android.view.ViewGroup" bounds="[42,1604][595,1655]"
          text="Suggestions pour vous" content-desc="Suggestions pour vous"/>
    <node class="android.view.ViewGroup" bounds="[790,1604][963,1655]"
          text="Voir tout" content-desc="Voir tout"/>
  </node>
</hierarchy>
"""

# The same labels, but belonging to two different rows: a "See all" that heads another feed
# section must never be taken for the suggestions CTA.
COMPOSE_OTHER_SECTION = """
<hierarchy>
  <node class="android.view.ViewGroup" bounds="[0,900][1080,1040]" content-desc="">
    <node class="android.view.ViewGroup" bounds="[42,944][595,995]"
          text="Reels populaires" content-desc="Reels populaires"/>
    <node class="android.view.ViewGroup" bounds="[790,944][963,995]"
          text="Voir tout" content-desc="Voir tout"/>
  </node>
</hierarchy>
"""


def test_the_compose_carousel_is_found_without_a_single_resource_id():
    carousel = parse_feed_suggestions_carousel(
        etree.fromstring(COMPOSE_CAROUSEL.encode()), FEED_SUGGESTIONS_SELECTORS
    )
    assert carousel["present"] is True
    assert carousel["title"] == "Suggestions pour vous"
    assert carousel["cta_bounds"] == (790, 1604, 963, 1655)


def test_a_see_all_heading_another_section_is_not_the_carousel():
    carousel = parse_feed_suggestions_carousel(
        etree.fromstring(COMPOSE_OTHER_SECTION.encode()), FEED_SUGGESTIONS_SELECTORS
    )
    assert carousel["present"] is False
    assert carousel["cta_bounds"] is None


def test_a_cta_left_of_its_header_is_not_paired():
    # Guards the geometry rather than the labels: the CTA sits at the right end of the row.
    mirrored = COMPOSE_CAROUSEL.replace('bounds="[790,1604][963,1655]"', 'bounds="[10,1604][40,1655]"')
    carousel = parse_feed_suggestions_carousel(
        etree.fromstring(mirrored.encode()), FEED_SUGGESTIONS_SELECTORS
    )
    assert carousel["cta_bounds"] is None
