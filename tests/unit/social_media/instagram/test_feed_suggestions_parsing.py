"""Parsing des suggestions de comptes (carousel feed + ecran Discover people).

Les dumps ci-dessous sont des extraits ANONYMISES d'une capture reelle
(device 9CHAY1PN, Instagram v410.0.0.53.71, 2026-07-26) : la structure, les
resource-id et les libelles de bouton sont ceux du device, les noms de comptes
ont ete remplaces.

Ce qui est verrouille ici :
- le CTA "See all" du carousel est lu avec ses bounds (point d'entree du mode) ;
- une ligne 'Follow back' n'est JAMAIS proposee au follow (le follow-back
  appartient au workflow Notifications) ;
- une ligne deja 'Following' / 'Requested' n'est pas re-tapee ;
- la section d'appartenance d'une ligne est resolue par position verticale ;
- les lignes d'accroche "Connect contacts" / "Connect to Facebook" ne sont pas
  prises pour des suggestions.
"""

import pytest

from lxml import etree

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
    """Une ligne de recommandation telle qu'IG la rend (bouton dans le sous-arbre)."""
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


# --- carousel du feed --------------------------------------------------------

def test_carousel_exposes_its_cta_and_cards():
    carousel = parse_feed_suggestions_carousel(_root(FEED_CAROUSEL_DUMP),
                                               FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is True
    assert carousel["title"] == "Suggested for you"
    # Le CTA est tape sur ses bounds reelles, jamais sur une coordonnee en dur.
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


# --- ecran Discover people ---------------------------------------------------

def test_discover_screen_is_recognised_structurally():
    assert is_discover_people_screen(_root(DISCOVER_DUMP), DISCOVER_PEOPLE_SELECTORS) is True
    assert read_screen_title(_root(DISCOVER_DUMP)) == "Discover people"


def test_a_username_alone_is_not_the_discover_screen():
    """Un `row_recommended_user_username` isole (queue d'une liste followers) ne
    doit pas etre pris pour l'ecran de suggestions."""
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
    """Regle metier : ni follow-back, ni demande en attente, ni deja suivi."""
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
