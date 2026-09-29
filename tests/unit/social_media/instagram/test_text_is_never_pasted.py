"""A text the bot types goes through its own keyboard, or is not typed at all.

When the Taktik Keyboard could not type, the typing paths wrote the text another way: `set_text`
(accessibility), `adb shell input text`, uiautomator2's `send_keys`. Each writes the whole text
at once through a keyboard that is not the one on screen, no key pressed: a signal no person gives.
The action now fails, says so in the log and reports its failure like any other; nothing is
pasted. The login keeps its rescue until Kevin decides (the last test pins it).

The phone is the folding field of `test_keyboard_switched_before_the_field_is_tapped.py`, with a
Taktik Keyboard that answers no broadcast (adb returns nothing): it types and clears nothing, and
every text written another way is listed.
"""

import pytest

from taktik.core.shared.input.keyboard import KeyboardService
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.workflows.cold_dm.search import ColdDMSearchMixin

from test_keyboard_switched_before_the_field_is_tapped import (  # noqa: F401 (fixture)
    TEXT,
    FoldingFieldPhone,
    _cold_dm_bridge,
    _comment_action,
    _dm_bridge,
    _login_password,
    _notifications,
    _on_the_phone,
    _post_caption,
    _signup_field,
    _story_reply,
    _text_actions_field,
    phone,
)


@pytest.fixture
def no_keyboard(monkeypatch):
    return _on_the_phone(FoldingFieldPhone(keyboard_answers=False), monkeypatch)


def _pasted(phone):
    return phone.set_texts + phone.pasted


# -- The DM composer and the DM bridges ------------------------------------------------------------

def test_a_dm_the_keyboard_cannot_type_is_not_pasted(no_keyboard):
    assert dm_composer.type_message(no_keyboard, None, TEXT) is False

    assert _pasted(no_keyboard) == [] and no_keyboard.field == ""


@pytest.mark.parametrize("bridge", [_dm_bridge, _cold_dm_bridge], ids=["dm", "cold_dm"])
def test_a_dm_bridge_sends_nothing_the_keyboard_could_not_type(no_keyboard, bridge):
    assert not bridge(no_keyboard).send_message(TEXT)

    assert _pasted(no_keyboard) == [] and no_keyboard.presses == []


# -- The comment, the threaded reply, the reply from the notifications ------------------------------

def test_a_comment_the_keyboard_cannot_type_is_not_pasted(no_keyboard):
    assert _comment_action(no_keyboard)._type_comment(TEXT) is False

    assert _pasted(no_keyboard) == []


def test_a_threaded_reply_the_keyboard_cannot_type_is_not_pasted(no_keyboard):
    comment = _comment_action(no_keyboard)
    reply_bounds = no_keyboard.add_button("reply", no_keyboard.focus_with("@ana "))
    comment.default_config = {"comment_delay_range": (0, 0)}
    comment._is_comments_view_open = lambda: True
    comment._find_comment_reply_control = lambda _handle: reply_bounds
    posted = []
    comment._post_comment = lambda: posted.append(no_keyboard.field) or True
    comment._record_posted_comment = lambda *_a, **_k: 1
    comment._close_comment_popup = lambda: True

    result = comment.reply_to_comment_in_thread("ana", TEXT)

    assert result["success"] is False and result["message"] == "Could not type the reply"
    assert _pasted(no_keyboard) == [] and posted == []


def test_a_reply_that_lost_its_mention_gets_it_back_from_the_keyboard(phone):
    """The Reply opened the composer without its "@ana ": the checked typing empties the field
    and types the mention with the reply, through the keyboard. Nothing rewrites the field."""
    comment = _comment_action(phone)
    reply_bounds = phone.add_button("reply", phone.focus_with(""))
    comment.default_config = {"comment_delay_range": (0, 0)}
    comment._is_comments_view_open = lambda: True
    comment._find_comment_reply_control = lambda _handle: reply_bounds
    posted = []
    comment._post_comment = lambda: posted.append(phone.field) or True
    comment._record_posted_comment = lambda *_a, **_k: 1
    comment._close_comment_popup = lambda: True

    assert comment.reply_to_comment_in_thread("ana", TEXT)["success"] is True

    assert posted == ["@ana " + TEXT] and _pasted(phone) == []


def test_a_notification_reply_the_keyboard_cannot_type_is_not_pasted(no_keyboard):
    assert _notifications(no_keyboard)._type_into(no_keyboard.field_node(), TEXT) is False

    assert _pasted(no_keyboard) == []


# -- The fields typed through TextActions (the base typing) -----------------------------------------

@pytest.mark.parametrize("fill", [
    _signup_field, _post_caption, _story_reply, _text_actions_field,
], ids=["signup", "post_caption", "story_reply", "text_actions_field"])
def test_a_field_the_keyboard_cannot_type_is_not_pasted(no_keyboard, fill):
    filled, _text = fill(no_keyboard)

    assert filled is False
    assert _pasted(no_keyboard) == []


# -- The cold DM search -----------------------------------------------------------------------------

def _cold_dm_search(phone):
    class _Search(ColdDMSearchMixin):
        device = phone
        _keyboard = KeyboardService(phone.device_id)

    phone._fields.append({"resourceId": NAVIGATION_SELECTORS.explore_search_bar_resource_id})
    return _Search()


def test_the_cold_dm_search_is_typed_by_the_keyboard(phone):
    """It wrote the handle with `set_text`, the keyboard never used."""
    _cold_dm_search(phone).search_user("ana")

    assert phone.steps == ["switch", "tap"]
    assert phone.field == "ana" and _pasted(phone) == []


def test_a_cold_dm_search_the_keyboard_cannot_type_is_not_pasted(no_keyboard):
    assert _cold_dm_search(no_keyboard).search_user("ana") is False

    assert _pasted(no_keyboard) == [] and no_keyboard.field == ""


# -- The login, apart until Kevin decides -----------------------------------------------------------

def test_the_login_still_pastes_when_the_keyboard_cannot_type(no_keyboard):
    """Its rescue is kept as it was (`paste_if_keyboard_fails`): `adb shell input text`. A
    failure there would be a login that stops at its password field."""
    filled, text = _login_password(no_keyboard)

    assert filled is True
    assert no_keyboard.pasted == [text]
