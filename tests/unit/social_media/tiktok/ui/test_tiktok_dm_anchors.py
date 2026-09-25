"""DM fields that were reachable through a build id only now have a route that survives a version:
structure, attributes and, where the words are the anchor, the French locale.

The screens reproduce the SHAPE of conversation and inbox captures of TikTok 43.1.4 and 46.9.3, as
the device dumps them, evaluated by uiautomator2's own `d.xpath()` engine. They carry no
resource-id at all, so only the new routes can answer. Names, texts and dates are invented.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import INBOX_SELECTORS

RV = "androidx.recyclerview.widget.RecyclerView"
TEXT_43 = "im.messagelist.api.ui.IMTuxTextLayoutView"
TEXT_46 = "X.a1b2"
VIEW = "android.view.View"
LRM = "\u200e"


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _n(cls, text="", desc="", clickable=False, long=False, focusable=False, children=""):
    cls = cls if "." in cls else f"android.widget.{cls}"
    attrs = (f'class="{cls}" text="{text}" content-desc="{desc}" resource-id="" '
             f'clickable="{str(clickable).lower()}" long-clickable="{str(long).lower()}" '
             f'focusable="{str(focusable).lower()}" bounds="[0,0][10,10]"')
    return f"<node {attrs}>{children}</node>"


def _screen(*body):
    clock = _n("TextView", "00:00", desc="00:00")
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{clock}{"".join(body)}</hierarchy>'


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _found(selectors, xml):
    """Every node the field resolves to, the way `first_matching` walks it (first answer wins)."""
    device = _Device(xml)
    for selector in selectors:
        found = device.xpath(selector).all()
        if found:
            return found
    return []


# --- conversation, 43.1.4 shape --------------------------------------------------------------

def _date_43(label):
    return _n("LinearLayout", children=_n("TextView", label))


def _bubble_43(text):
    return _n("FrameLayout", children=_n("FrameLayout", long=True, children=_n(
        "LinearLayout", children=_n(TEXT_43, text, focusable=True))))


AVATAR_43 = _n("FrameLayout", children=_n("TextView", desc="Alex", clickable=True, focusable=True))
STICKER_43 = _n("FrameLayout", children=_n("FrameLayout", desc="Stickers", clickable=True, long=True,
                                           children=_n("ImageView")))
PROFILE_CARD = _n("Button", children=_n("LinearLayout", clickable=True, children=(
    _n("TextView", "Alex") + _n("TextView", "@alex") + _n("TextView", "12 suivis · 34 followers"))))
SUGGESTION_CARD = _n("LinearLayout", children=(
    _n("RelativeLayout", children=_n("TextView", "Ça fait longtemps. Dis bonjour !")
       + _n("ImageView", desc="Fermer", clickable=True))
    + _n("RelativeLayout", children=_n(RV, focusable=True, children=_n("ImageView", clickable=True)))))
REACTIONS = _n(RV, children="".join(
    _n("LinearLayout", clickable=True, children=_n("Button", desc=name)) for name in ("Heart", "Lol")))
COMPOSER = _n("EditText", "Message…", clickable=True)

CONVERSATION_43 = _screen(
    _n("FrameLayout", desc="Retour", clickable=True),
    _n(RV, clickable=True, children=(
        PROFILE_CARD
        + _date_43("1 janv., 00:00")
        + _n("ViewGroup", children=_n(VIEW) + _bubble_43("Bonjour")
             + _n("FrameLayout", children=_n("TextView", "Vu")))
        + _date_43("2 janv., 00:00")
        + _n("TextView", "Demande de message acceptée.")
        + _date_43("Aujourd'hui 00:00")
        + _n("ViewGroup", children=AVATAR_43 + _n(VIEW) + _bubble_43("Merci"))
        + _n("ViewGroup", children=AVATAR_43 + STICKER_43)
        + SUGGESTION_CARD)),
    REACTIONS,
    COMPOSER,
)

# --- conversation, 46.9.3 shape --------------------------------------------------------------


def _date_46(label):
    return _n("FrameLayout", children=_n("FrameLayout", children=_n("TextView", label)))


def _avatar_46(desc):
    return _n("FrameLayout", children=_n("FrameLayout", clickable=True, children=_n(
        "FrameLayout", children=_n("TextView", desc=desc))))


def _bubble_46(text):
    return _n("FrameLayout", long=True, children=_n("FrameLayout", clickable=True, children=_n(
        "LinearLayout", children=_n(TEXT_46, text, focusable=True))))


STICKER_46 = _n("FrameLayout", long=True, children=_n("FrameLayout", desc="Stickers", clickable=True,
                                                      children=_n("ImageView")))
SEEN_46 = _n("FrameLayout", clickable=True, children=_n("ViewSwitcher", children=_n(
    "TextView", "Vu", focusable=True)))
REPLY_CHIP = _n("FrameLayout", children=_n("LinearLayout", children=_n("Button", "Répondre", clickable=True)))

CONVERSATION_46 = _screen(
    _n("FrameLayout", desc="Retour", clickable=True),
    _n(RV, clickable=True, children=(
        _n("FrameLayout", children=_n("FrameLayout", children=_n("TextView", "Demande de message acceptée.")))
        + _date_46("1 janv., 00:00")
        + _n("ViewGroup", children=_avatar_46("Alex") + _n(VIEW) + _bubble_46("Bonjour"))
        + _date_46("Aujourd'hui 00:00")
        + _n("ViewGroup", children=STICKER_46 + _n(VIEW) + SEEN_46)
        + _n("ViewGroup", children=_avatar_46("") + _n(VIEW) + STICKER_46 + REPLY_CHIP))),
    COMPOSER,
)

LONG_PRESS_MENU_43 = _screen(_n("FrameLayout", desc="Panneau", clickable=True, children=_n(RV, children="".join(
    _n("LinearLayout", clickable=True, children=_n("ImageView", desc=icon) + _n("TextView", label))
    for icon, label in (("Répondre", "Répondre"), ("Partager", "Transférer"), ("Copier", "Copier"))))))

# --- inbox -----------------------------------------------------------------------------------


def _story(name, avatar=True):
    inner = _n("RelativeLayout", clickable=True, long=True, children=_n("ImageView")) if avatar \
        else _n("ViewGroup", children=_n("ImageView", clickable=True))
    return _n("ViewGroup", desc=name, clickable=True, long=True, children=inner + _n("TextView", name))


STORIES = _n(RV, focusable=True, children=_story("Créer") + _story("Sam") + _story("+ Widget", avatar=False))


def _row(name, preview, right=""):
    return _n("ViewGroup", clickable=True, long=True, children=(
        _n("RelativeLayout", clickable=True, long=True, children=_n("TextView", desc=name))
        + _n("LinearLayout", children=_n("TextView", LRM + name) + _n("TextView", preview))
        + _n("LinearLayout", long=True, children=right)))


UNREAD = _n("FrameLayout", children=_n(VIEW, desc="1", focusable=True))
BOTTOM_BAR = _n("LinearLayout", children=(
    _n("FrameLayout", desc="Accueil", clickable=True, children=_n("TextView", "Accueil") + _n("ImageView"))
    + _n("FrameLayout", desc="Messages", clickable=True, children=_n("TextView", "2") + _n("TextView", "Messages"))))

INBOX_43 = _screen(
    _n("TextView", "Messages"),
    _n(RV, children=(
        STORIES
        + _n("Button", clickable=True, long=True, children=_n("TextView", "Activité")
             + _n("ViewGroup", children=_n(VIEW, desc="1", focusable=True)))
        + _row("Sam", "Merci", right=UNREAD))),
    BOTTOM_BAR,
)

INBOX_46 = _screen(
    _n("TextView", "Messages"),
    _n(RV, children=(
        STORIES
        + _row("Sam", LRM + "Vu")
        + _row("Lou", LRM + "Envoyé")
        + _row("Noa", LRM + "Salut", right=UNREAD)
        + _row("Demandes de messages", LRM + "Tu as reçu 1 demande"))),
    BOTTOM_BAR,
)

REQUESTS_PAGE = _screen(
    _n("TextView", "Demandes de messages (1)", desc="Demandes de messages (1)"),
    _n(RV, children=_n("LinearLayout", clickable=True, long=True, children=(
        _n("FrameLayout", children=_n("TextView", desc="Sam"))
        + _n("LinearLayout", children=_n("TextView", "Sam") + _n("TextView", LRM + "Salut"))
        + _n("LinearLayout", children=_n(VIEW, desc="1", focusable=True))))),
)

# --- screens where none of these fields may answer -------------------------------------------

COMMENT_SHEET = _screen(
    _n(RV, children=_n("LinearLayout", children=_n("ViewGroup", children=(
        _n("ImageView", clickable=True) + _n("Button", "Alex", clickable=True)
        + _n("TextView", "Rendez-vous à 00:00", focusable=True)
        + _n("LinearLayout", children=_n("TextView", "2 j") + _n("Button", "Répondre", clickable=True)))))),
    _n("FrameLayout", children=_n("EditText", "Ajouter un commentaire…", clickable=True)
       + _n("ImageView", desc="Stickers", clickable=True)),
)

GALLERY = _screen(_n(RV, children=_n("FrameLayout", clickable=True, long=True, children=(
    _n("ImageView") + _n("FrameLayout", children=_n(VIEW) + _n("TextView", "00:15"))))))

ELSEWHERE = {"comment_sheet": COMMENT_SHEET, "gallery": GALLERY, "inbox_43": INBOX_43,
             "inbox_46": INBOX_46, "requests": REQUESTS_PAGE}

CONVERSATION_FIELDS = ["date_separator", "date_text", "message_sender_avatar", "message_sticker",
                       "reply_button", "sticker_suggestion"]
INBOX_FIELDS = ["unread_badge", "message_request_unread_badge", "seen_marker", "stories_row",
                "story_username"]


@pytest.mark.parametrize("name", CONVERSATION_FIELDS)
def test_a_conversation_field_keeps_its_build_id_first(name):
    assert ":id/" in getattr(CONVERSATION_SELECTORS, name)[0]


@pytest.mark.parametrize("name", INBOX_FIELDS)
def test_an_inbox_field_keeps_its_build_id_first(name):
    assert ":id/" in getattr(INBOX_SELECTORS, name)[0]


@pytest.mark.parametrize("screen", [CONVERSATION_43, CONVERSATION_46], ids=["43", "46"])
def test_dates_are_the_list_rows_that_carry_a_time(screen):
    texts = [el.text for el in _found(CONVERSATION_SELECTORS.date_text, screen)]
    assert texts[0] == "1 janv., 00:00" and texts[-1] == "Aujourd'hui 00:00"
    assert "Demande de message acceptée." not in texts
    assert len(_found(CONVERSATION_SELECTORS.date_separator, screen)) == len(texts)


def test_the_status_bar_clock_is_not_a_date():
    assert all(el.attrib.get("content-desc") == "" for el in _found(CONVERSATION_SELECTORS.date_text, CONVERSATION_43))


@pytest.mark.parametrize("screen, expected", [(CONVERSATION_43, 2), (CONVERSATION_46, 2)], ids=["43", "46"])
def test_the_avatar_is_the_tap_target_beside_a_received_message(screen, expected):
    found = _found(CONVERSATION_SELECTORS.message_sender_avatar, screen)
    assert len(found) == expected
    assert all(el.attrib.get("clickable") == "true" for el in found)


def test_the_avatar_names_the_sender_on_43():
    assert {el.attrib.get("content-desc") for el in
            _found(CONVERSATION_SELECTORS.message_sender_avatar, CONVERSATION_43)} == {"Alex"}


@pytest.mark.parametrize("screen, expected", [(CONVERSATION_43, 1), (CONVERSATION_46, 2)], ids=["43", "46"])
def test_sticker_bubbles_are_found(screen, expected):
    assert len(_found(CONVERSATION_SELECTORS.message_sticker, screen)) == expected


def test_the_reply_entry_of_the_long_press_menu_is_found_and_only_it():
    found = _found(CONVERSATION_SELECTORS.reply_button, LONG_PRESS_MENU_43)
    assert len(found) == 1
    assert found[0].elem.xpath("./*[@content-desc='Répondre']")


def test_the_reply_chip_beside_a_sticker_is_found():
    found = _found(CONVERSATION_SELECTORS.reply_button, CONVERSATION_46)
    assert [el.text for el in found] == ["Répondre"]


def test_the_sticker_suggestion_card_is_found_on_43():
    assert len(_found(CONVERSATION_SELECTORS.sticker_suggestion, CONVERSATION_43)) == 1
    assert _found(CONVERSATION_SELECTORS.sticker_suggestion, CONVERSATION_46) == []


@pytest.mark.parametrize("name", CONVERSATION_FIELDS)
@pytest.mark.parametrize("where", sorted(ELSEWHERE))
def test_no_conversation_field_answers_outside_a_conversation(name, where):
    assert _found(getattr(CONVERSATION_SELECTORS, name), ELSEWHERE[where]) == []


@pytest.mark.parametrize("screen, expected", [(INBOX_43, 2), (INBOX_46, 1), (REQUESTS_PAGE, 1)],
                         ids=["inbox_43", "inbox_46", "requests"])
def test_unread_counts_are_row_badges_not_the_bottom_bar(screen, expected):
    for field in (INBOX_SELECTORS.unread_badge, INBOX_SELECTORS.message_request_unread_badge):
        assert [el.attrib.get("content-desc") for el in _found(field, screen)] == ["1"] * expected


def test_the_seen_preview_is_read_through_its_direction_mark():
    found = _found(INBOX_SELECTORS.seen_marker, INBOX_46)
    assert [el.text for el in found] == [LRM + "Vu"]


def test_the_seen_label_under_a_message_is_not_the_inbox_marker():
    assert _found(INBOX_SELECTORS.seen_marker, CONVERSATION_46) == []
    assert _found(INBOX_SELECTORS.seen_marker, CONVERSATION_43) == []


@pytest.mark.parametrize("screen", [INBOX_43, INBOX_46], ids=["43", "46"])
def test_stories_are_the_tiles_with_an_avatar(screen):
    assert [el.text for el in _found(INBOX_SELECTORS.story_username, screen)] == ["Créer", "Sam"]
    assert len(_found(INBOX_SELECTORS.stories_row, screen)) == 2


@pytest.mark.parametrize("name", INBOX_FIELDS)
@pytest.mark.parametrize("screen", [CONVERSATION_43, CONVERSATION_46, COMMENT_SHEET, GALLERY],
                         ids=["conversation_43", "conversation_46", "comment_sheet", "gallery"])
def test_no_inbox_field_answers_outside_the_inbox(name, screen):
    assert _found(getattr(INBOX_SELECTORS, name), screen) == []


def test_english_keeps_the_neutral_routes_and_drops_the_french_words():
    set_active_locale("en")
    assert len(_found(CONVERSATION_SELECTORS.date_text, CONVERSATION_46)) == 2
    assert len(_found(CONVERSATION_SELECTORS.message_sender_avatar, CONVERSATION_46)) == 2
    assert _found(CONVERSATION_SELECTORS.message_sticker, CONVERSATION_46) == []
    assert _found(CONVERSATION_SELECTORS.reply_button, CONVERSATION_46) == []
