"""Parsing of the account suggestions (feed carousel and discovery screen), on real screens.

The screens are real captures, anonymized:

- Instagram 410 in French (Pixel 4a, 2026-09-28): the feed carousel « Suggestions pour vous »
  and the « Contacts à découvrir » screen opened by its « Voir tout »;
- Instagram 410 in English (Pixel 3a): the framed feed carousel and « Discover people »;
- Instagram 410 in French (Pixel 3, 2026-09-24): the end of a following list, where Instagram
  appends a « Suggestions » tail, and the search screen with its « Récent · Voir tout » row;
- Instagram 447 in French (Pixel 6a): the feed carousel rebuilt without a resource-id (first
  seen on 442, 2026-08-26).

What is locked here:
- the carousel CTA is read with its bounds, being the entry point of the mode;
- a follow-back row is NEVER offered to the follow, since follow-back belongs
  to the notifications workflow;
- an already-followed row is not tapped again;
- the section a row belongs to is resolved by vertical position;
- the call-to-action rows are not taken for suggestions.

No capture holds a « Requested » row (it needs a follow request sent) nor the other French verb
family (« S'abonner ») on a list: those labels are tested on their own, as labels.
"""

from pathlib import Path

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
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
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parent / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _root(name):
    return parse_ui_dump(_capture(name))


@pytest.fixture
def app_language():
    yield set_active_locale
    set_active_locale(None)


# --- feed carousel -----------------------------------------------------------

CAROUSELS = {
    "fr": ("ig410_fr_feed_suggestions_carousel.xml", "Suggestions pour vous", (498, 306, 660, 356),
           [("name_8 and name_9 and name_10", "Suivre", (72, 1021, 624, 1109)),
            ("name_11 name_12", "Suivre", (723, 1021, 1080, 1109))]),
    "en": ("ig410_en_feed_carousel_framed.xml", "Suggested for you", (880, 787, 1036, 837),
           [("Mara Quill", "Follow", (72, 1502, 624, 1590)),
            ("Teo Varnish", "Follow", (723, 1502, 1080, 1590))]),
}


@pytest.mark.parametrize("language", ["fr", "en"])
def test_carousel_exposes_its_cta_and_cards(app_language, language):
    name, title, cta, cards = CAROUSELS[language]
    app_language(language)
    carousel = parse_feed_suggestions_carousel(_root(name), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is True
    assert carousel["title"] == title
    # The CTA is tapped on its real bounds, never on a hardcoded coordinate.
    assert carousel["cta_bounds"] == cta
    assert [(c["name"], c["state_label"], c["follow_bounds"]) for c in carousel["cards"]] == cards


def test_carousel_absent_from_a_plain_feed_dump():
    carousel = parse_feed_suggestions_carousel(_root("ig410_fr_home_feed.xml"), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is False
    assert carousel["cta_bounds"] is None


# --- people discovery screen -------------------------------------------------

DISCOVER = {"fr": ("ig410_fr_discover_people.xml", "Contacts à découvrir"),
            "en": ("ig410_en_discover_people.xml", "Discover people")}


@pytest.mark.parametrize("language", ["fr", "en"])
def test_discover_screen_is_recognised_structurally(app_language, language):
    name, title = DISCOVER[language]
    app_language(language)
    assert is_discover_people_screen(_root(name), DISCOVER_PEOPLE_SELECTORS) is True
    assert read_screen_title(_root(name)) == title


def test_a_screen_without_recommendation_rows_is_not_the_discover_screen():
    """The feed carousel holds suggestion cards, not recommendation rows."""
    root = _root("ig410_fr_feed_suggestions_carousel.xml")
    assert is_discover_people_screen(root, DISCOVER_PEOPLE_SELECTORS) is False


def test_the_suggestions_tail_of_a_following_list_is_not_the_discover_screen():
    """Instagram appends suggestion rows, container and button included, at the end of a
    following list. The surface proof used to be « a row container with its button », which it
    assumed only the discovery screen shows: the real tail proved it wrong."""
    root = _root("ig410_fr_following_list_suggestions_tail.xml")
    assert parse_suggestion_rows(root, DISCOVER_PEOPLE_SELECTORS, PROFILE_SELECTORS,
                                 classify_follow_state)
    assert is_discover_people_screen(root, DISCOVER_PEOPLE_SELECTORS) is False


ROWS = {
    "fr": [
        ("name_6 name_7 name_8 boutique", "follow", "Suggestions pour vous"),
        ("name_9 name_10", "follow", "Suggestions pour vous"),
        ("name_11 J name_12", "follow", "Suggestions pour vous"),
        ("user_1", "follow", "Suggestions pour vous"),
        ("name_13 name_14", "follow", "Suggestions pour vous"),
        ("user_2", "follow_back", "Suivre en retour"),
    ],
    "en": [
        ("name_2 name_3", "follow_back", "Suggested for you"),
        ("..", "following", "Suggested for you"),
        ("3 name_4 name_5", "follow_back", "Suggested for you"),
        ("name_7 name_8", "follow_back", "Suggested for you"),
        ("name_9 name_10", "following", "Suggested for you"),
    ],
}


def _rows(language):
    set_active_locale(language)
    return parse_suggestion_rows(_root(DISCOVER[language][0]), DISCOVER_PEOPLE_SELECTORS,
                                 PROFILE_SELECTORS, classify_follow_state)


@pytest.mark.parametrize("language", ["fr", "en"])
def test_rows_are_read_with_their_state_and_section(app_language, language):
    rows = _rows(language)
    assert [(row["label"], row["state"], row["section"]) for row in rows] == ROWS[language]


def test_connect_rows_are_not_suggestions(app_language):
    """The « Se connecter à Facebook » and « Importer vos contacts » rows head the French
    screen, each with its own button."""
    xml = _capture(DISCOVER["fr"][0])
    assert "Se connecter à Facebook" in xml and "Importer vos contacts" in xml
    labels = [row["label"] for row in _rows("fr")]
    assert not any("Facebook" in label or "contacts" in label for label in labels)


@pytest.mark.parametrize("language, followable", [
    ("fr", ["name_6 name_7 name_8 boutique", "name_9 name_10", "name_11 J name_12", "user_1",
            "name_13 name_14"]),
    ("en", []),
])
def test_only_plain_follow_rows_are_followable(app_language, language, followable):
    """Business rule: no follow-back, no already-followed. The French screen mixes follow rows
    and a follow-back one; the English screen holds only follow-back and following rows."""
    targets = followable_rows(_rows(language))
    assert [row["label"] for row in targets] == followable
    assert all(row["follow_bounds"] for row in targets)


@pytest.mark.parametrize("language, headers", [
    ("fr", ["Suggestions pour vous", "Suivre en retour"]),
    ("en", ["Suggested for you", "Follow requests"]),
])
def test_section_headers_are_ordered_top_down(language, headers):
    found = parse_section_headers(_root(DISCOVER[language][0]), DISCOVER_PEOPLE_SELECTORS)
    assert [header["label"] for header in found] == headers


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
    set_active_locale('fr')
    try:
        assert classify_follow_state("Suivre", PROFILE_SELECTORS) == 'follow'
        assert classify_follow_state("S'abonner", PROFILE_SELECTORS) == 'follow'
        assert classify_follow_state("S’abonner", PROFILE_SELECTORS) == 'follow'
        # The order still matters: the follow-back label contains the follow one.
        assert classify_follow_state("Suivre en retour", PROFILE_SELECTORS) == 'follow_back'
        assert classify_follow_state("S’abonner en retour", PROFILE_SELECTORS) == 'follow_back'
        assert classify_follow_state("Abonné", PROFILE_SELECTORS) == 'following'
    finally:
        set_active_locale(None)


# ── IG 442 and later: the carousel kept its shape and lost every resource-id ─────────────
#
# `netego_carousel_*` is absent from the dump ENTIRELY -- header and CTA are two labelled
# ViewGroups on one row, and nothing else marks the block. Since that CTA is the only entry point
# to the people-discovery screen in the whole codebase, losing it made the surface unreachable
# rather than merely undetected. Seen on 442 (2026-08-26), the capture below is 447.
COMPOSE = "ig447_fr_feed_suggestions_carousel.xml"
COMPOSE_CTA = (790, 454, 963, 505)
# A « Voir tout » heading another block: the search screen's « Récent » row (410, French).
OTHER_SECTION = "ig410_fr_search_recent_see_all.xml"


def test_the_compose_carousel_is_found_without_a_single_resource_id():
    xml = _capture(COMPOSE)
    assert "netego_carousel" not in xml
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(xml), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is True
    assert carousel["title"] == "Suggestions pour vous"
    assert carousel["cta_bounds"] == COMPOSE_CTA


def test_a_see_all_heading_another_section_is_not_the_carousel():
    xml = _capture(OTHER_SECTION)
    assert 'text="Voir tout"' in xml and 'text="Récent"' in xml
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(xml), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["present"] is False
    assert carousel["cta_bounds"] is None


# The carousel's words come from the server, not from the app's language: an English app
# (Pixel 3a, IG 410) showed "Suggestions pour vous" / "Voir tout", and 31 carousels of French
# apps read "Suggested for you" / "See all". On 410 the CTA's id finds it whatever the words;
# from 442 on the words are all there is. The English-worded Compose carousel is the real 447
# capture with its two labels translated (derived, no capture holds it).
def _english_worded_compose():
    return (_capture(COMPOSE).replace('"Suggestions pour vous"', '"Suggested for you"')
            .replace('"Voir tout"', '"See all"'))


@pytest.mark.parametrize("language, words", [("en", "french"), ("fr", "english")],
                         ids=["french-words-english-app", "english-words-french-app"])
def test_the_compose_carousel_is_found_in_the_other_language(app_language, language, words):
    app_language(language)
    root = parse_ui_dump(_capture(COMPOSE) if words == "french" else _english_worded_compose())

    carousel = parse_feed_suggestions_carousel(root, FEED_SUGGESTIONS_SELECTORS)

    assert carousel["cta_bounds"] == COMPOSE_CTA
    assert any(root.xpath(selector) for selector in FEED_SUGGESTIONS_SELECTORS.carousel_see_all)


@pytest.mark.parametrize("language", ["en", "fr"])
def test_a_see_all_heading_another_section_is_not_the_carousel_in_either_language(app_language, language):
    app_language(language)
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(_capture(OTHER_SECTION)),
                                               FEED_SUGGESTIONS_SELECTORS)
    assert carousel["cta_bounds"] is None


def test_a_cta_left_of_its_header_is_not_paired():
    # Guards the geometry rather than the labels: the CTA sits at the right end of the row.
    # The real 447 carousel with its CTA moved to the left edge (derived).
    mirrored = _capture(COMPOSE).replace('bounds="[790,454][963,505]"', 'bounds="[10,454][40,505]"')
    assert mirrored != _capture(COMPOSE)
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(mirrored), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["cta_bounds"] is None


def test_the_compose_cards_are_read_from_their_follow_control():
    """Only the follow control kept an id, and it names its own target: « Suivre <name> ». The
    follow-back card of the real carousel names nobody (its description is the label alone), so
    it yields no name rather than a wrong one."""
    carousel = parse_feed_suggestions_carousel(_root(COMPOSE), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["cards"] == [
        {"name": "", "state_label": "Suivre en retour", "follow_bounds": (69, 1154, 643, 1238)},
        {"name": "name_16 name_17 name_18", "state_label": "Suivre",
         "follow_bounds": (739, 1154, 1080, 1238)},
    ]


def test_the_account_name_is_the_difference_between_desc_and_text():
    # No label list and therefore no language: the control says "Suivre <name>" and reads
    # "Suivre", so what is left is the account. The real card, its words in English (derived).
    english = _capture(COMPOSE).replace('text="Suivre" resource-id="com.instagram.android:id/inline_follow_button"',
                                        'text="Follow" resource-id="com.instagram.android:id/inline_follow_button"')
    english = english.replace('content-desc="Suivre name_16 name_17 name_18"',
                              'content-desc="Follow name_16 name_17 name_18"')
    assert english.count('"Follow"') == 1 and "Follow name_16" in english
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(english), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["cards"][1]["name"] == "name_16 name_17 name_18"
    assert carousel["cards"][1]["state_label"] == "Follow"


def test_a_control_whose_description_does_not_start_with_its_label_yields_no_name():
    # Better an empty name than a wrong one: the caller records who it followed.
    odd = _capture(COMPOSE).replace('content-desc="Suivre name_16 name_17 name_18"',
                                    'content-desc="Abonnement a name_16 name_17 name_18"')
    carousel = parse_feed_suggestions_carousel(parse_ui_dump(odd), FEED_SUGGESTIONS_SELECTORS)
    assert carousel["cards"][1]["name"] == ""
    assert carousel["cards"][1]["follow_bounds"] == (739, 1154, 1080, 1238)
