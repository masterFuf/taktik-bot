"""A TikTok inbox row is acted on only when its name is the name asked for (`same_shown_name`).

The conversation a reply goes into, the wave sent from the inbox and the follower followed back
were each picked by inclusion: the first row whose name held the name asked for, or was held by
it. Measured on a C57S (TikTok 43.1.4, English, 2026-10-25): « demo_fan🦋 » sits right under
« 1NE demo_fan ft AP », so `click_conversation("demo_fan")` opened the second account's
conversation, the first row that held the name.

Inside the row, the button is the one that reads what the gesture is: the follow-back, the
wave. On 43.1.4 a new follower's row has one button whose label is its state (« Follow back »,
« Message », « Requested », « Send a » and a waving hand), always under the same id `rdh`; the inbox rows that read
« Say hi to … » have no wave button at all, and their last clickable is the camera shortcut.

The screens are real dumps, anonymized (`scripts/lab/anonymize_dump.py`, the same word gets the same
placeholder, so « demo_fan » reads `name_33`name_34` in both rows): the English inbox of that
phone and the conversation one of its rows opens, the French new-followers page of a Pixel 3a
(43.1.4), the English new-followers page of the C57S before and after one follow-back, and the
French new-followers page of a Pixel 6a on 47.0.3, where the button's id is another and only its
label is left to read. The phone answers `xpath` through uiautomator2's own engine and `d(resourceIdMatches=...)`
from the same dump; what a tap opens is written in `doors`, per test.
"""

import pytest

from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.social_media.tiktok.actions.screens_phone import ScreensPhone, install_test_clock, read_captures

SCREENS = read_captures(
    inbox="tt4314_en_inbox.xml",
    thread="tt4314_en_dm_thread.xml",
    new_followers="tt4314_fr_new_followers.xml",
    new_followers_en="tt4314_en_new_followers.xml",
    followed_back_en="tt4314_en_new_followers_followed_back.xml",
    new_followers_47="tt4703_fr_new_followers.xml",
)

#: The rows of the inbox, by the name each shows (the anonymiser's words).
GROUP_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200e...... name_33`name_34 name_35 ...."]]'
BUTTERFLY_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_33`name_34.."]]'
GRANNY_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_38"]]'
AUSTIN_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_40"]]'
#: The new-followers page: the row of user_1, who shows « Suivre en retour », and its button.
USER_1_FOLLOW_BACK = ('//*[contains(@resource-id, ":id/o0v")][.//*[@text="\u200e\u2068user_1\u2069"]]'
                      '//*[contains(@resource-id, ":id/rdh")]')
#: The English page of the C57S, before and after the one follow-back of 2026-10-25 (name_8).
NAME_8_BUTTON = ('//*[contains(@resource-id, ":id/o0v")][.//*[@text="‎⁨name_8⁩"]]'
                 '//*[contains(@resource-id, ":id/rdh")]')


def _phone(screen, doors):
    """The phone on `screen`; a tap inside an area of a screen in `doors` opens the screen named there."""
    return ScreensPhone(SCREENS, screen, doors)


def _inside(tap, screen, xpath):
    return ScreensPhone(SCREENS, screen).inside(tap, screen, xpath)


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    install_test_clock(monkeypatch)


@pytest.fixture
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


# --- the conversation a reply goes into -----------------------------------------------------------


@pytest.mark.parametrize("asked", [
    "name_33`name_34",  # the butterfly row's name without its emoji, held by the group row above it
    "name_3",           # the beginning of every row name_33..., name_38
    "name_35",          # a word of the group row
])
def test_a_name_a_row_only_holds_opens_no_conversation(asked, english):
    phone = _phone("inbox", {("inbox", GROUP_ROW): "thread", ("inbox", GRANNY_ROW): "thread"})

    assert DMActions(phone).click_conversation(asked) is False
    assert phone.taps == []


def test_the_row_of_the_name_opens_its_conversation(english):
    phone = _phone("inbox", {("inbox", GRANNY_ROW): "thread"})

    assert DMActions(phone).click_conversation("name_38") is True
    (tap,) = phone.taps
    assert _inside(tap, "inbox", GRANNY_ROW)


def test_a_name_read_with_its_emoji_opens_the_row_the_dump_shows_with_two_dots(english):
    """The selector API returns « demo_fan🦋 »; the dump, and so the conversation header a read
    returns, « demo_fan.. ». A reply holds either."""
    phone = _phone("inbox", {})

    DMActions(phone).click_conversation("name_33`name_34\U0001f98b")

    (tap,) = phone.taps
    assert _inside(tap, "inbox", BUTTERFLY_ROW)


def test_the_handle_is_read_only_off_the_thread_of_the_name(english):
    phone = _phone("inbox", {("inbox", GRANNY_ROW): "thread",
                             ("thread", '//*[@content-desc="Back"]'): "inbox"})

    assert DMActions(phone).resolve_conversation_handle("\u200ename_38") == "user_4"
    assert _inside(phone.taps[0], "inbox", GRANNY_ROW)


# --- the wave sent from the inbox -----------------------------------------------------------------


def test_a_wave_goes_to_no_row_whose_name_only_starts_with_the_name(english):
    phone = _phone("inbox", {})

    assert DMActions(phone).say_hello("name_4") is False
    assert phone.taps == []


def test_a_row_whose_line_only_previews_a_wave_is_not_tapped(english):
    """On 43.1.4 « Say hi to name_40 » is the row's preview line, and the row has no wave button:
    its last clickable is the camera shortcut, which the wave used to tap."""
    phone = _phone("inbox", {})

    assert DMActions(phone).say_hello("name_40") is False
    assert phone.taps == []


def test_no_wave_is_offered_by_rows_without_a_wave_button(english):
    """Two rows read « Say hi to … », neither has the button: nobody to greet from this inbox."""
    phone = _phone("inbox", {})

    assert DMActions(phone).say_hello_candidates() == []
    assert phone.taps == []


# --- the follower followed back -------------------------------------------------------------------


def test_no_follower_is_followed_back_for_a_name_that_only_starts_theirs(french):
    phone = _phone("new_followers", {})

    assert DMActions(phone).follow_back("user") is False
    assert phone.taps == []


def test_the_follower_of_the_name_is_followed_back(french):
    phone = _phone("new_followers", {})

    DMActions(phone).follow_back("user_1")

    (tap,) = phone.taps
    assert _inside(tap, "new_followers", USER_1_FOLLOW_BACK)


def test_a_follow_back_is_offered_only_to_the_row_of_the_name(french):
    phone = _phone("new_followers", {})

    followers = DMActions(phone).get_new_followers()

    assert [(f["username"], f["can_follow_back"]) for f in followers][1] == ("user_1", True)
    assert phone.taps == []


# --- the button of the row: « Message » shares the follow-back's id ------------------------------


def test_a_row_whose_button_reads_message_offers_no_follow_back(french):
    """name_1 is already followed: its row's only button reads « Message », under the same id `rdh`
    as « Suivre en retour ». The id alone said yes."""
    phone = _phone("new_followers", {})

    followers = DMActions(phone).get_new_followers()

    assert [(f["username"], f["can_follow_back"]) for f in followers] == [("name_1", False), ("user_1", True)]
    assert phone.taps == []


def test_the_message_button_is_never_tapped_as_a_follow_back(french):
    """Tapping it opens a conversation with that follower."""
    phone = _phone("new_followers", {})

    assert DMActions(phone).follow_back("name_1") is False
    assert phone.taps == []


@pytest.mark.parametrize("name", [
    "name_9",   # « Message »
    "user_1",   # « Requested »
    "name_10",  # « Send a » and a waving hand: a wave, a message
])
def test_a_button_that_is_not_the_follow_back_is_never_tapped(name, english):
    phone = _phone("new_followers_en", {})

    assert DMActions(phone).follow_back(name) is False
    assert phone.taps == []


def test_the_page_offers_a_follow_back_exactly_where_the_button_reads_it(english):
    phone = _phone("new_followers_en", {})

    followers = DMActions(phone).get_new_followers()

    assert [f["can_follow_back"] for f in followers] == [True, True, True, True, False, False, False, True, True]
    assert phone.taps == []


def test_a_follow_back_is_confirmed_once_the_button_no_longer_reads_it(english):
    """Measured on the C57S: after the tap, the same button, same id, offers the wave. Looked for by
    its id, the follow-back was « still there » and every follow-back came back unconfirmed."""
    phone = _phone("new_followers_en", {("new_followers_en", NAME_8_BUTTON): "followed_back_en"})

    assert DMActions(phone).follow_back("name_8") is True
    (tap,) = phone.taps
    assert _inside(tap, "new_followers_en", NAME_8_BUTTON)


def test_a_follower_already_followed_back_is_not_tapped_again(english):
    """A second pass on name_8 would have tapped the wave its button now offers."""
    phone = _phone("followed_back_en", {})

    assert DMActions(phone).follow_back("name_8") is False
    assert phone.taps == []


@pytest.mark.parametrize("name", [
    "user_3",  # « Message »
    "user_2",  # « Envoyer un » and a waving hand
])
def test_on_47_the_label_alone_keeps_other_buttons_untapped(name, french):
    """47.0.3: no `o0v`, no `rdh`; the row is found from its name button and the follow-back by its
    label alone."""
    phone = _phone("new_followers_47", {})

    assert DMActions(phone).follow_back(name) is False
    assert phone.taps == []


def test_on_47_the_follow_back_of_the_row_is_found_by_its_label(french):
    phone = _phone("new_followers_47", {})

    DMActions(phone).follow_back("name_8")

    (tap,) = phone.taps
    assert _inside(tap, "new_followers_47", '//node[@text="‎⁨name_8⁩"]'
                                            '/ancestor::node[@clickable="true"][1]//node[@text="Suivre en retour"]')
