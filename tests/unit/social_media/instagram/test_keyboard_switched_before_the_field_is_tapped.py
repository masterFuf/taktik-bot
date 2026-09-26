"""Every Instagram field the bot types into is tapped AFTER the switch to the Taktik Keyboard.

Measured on TikTok 47.0.3 / Android 16 (Pixel 6a): switching keyboards while a field is focused
hides the keyboard on screen, the field folds and drops its focus, and every text or backspace
sent after the switch lands nowhere. Instagram typed the same way (tap, then the switch inside
the typing). `FoldingFieldPhone` has that fold: only a tap made after the switch lets the text in.
"""

import base64
import types

import pytest

import taktik.core.shared.behavior.typing as typing_plan
import taktik.core.shared.device.adb as adb
import taktik.core.shared.input.taktik_keyboard as kb
from bridges.common.input.keyboard import KeyboardService
from taktik.core.social_media.instagram.workflows.dm_inbox.sender import DMSenderMixin
from taktik.core.social_media.instagram.actions.atomic.interaction.story_interaction import (
    StoryInteractionMixin,
)
from taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation import (
    SearchNavigationMixin,
)
from taktik.core.social_media.instagram.actions.atomic.text import TextActions, dm_composer
from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
from taktik.core.social_media.instagram.actions.business.management.content import (
    navigation as content_navigation,
)
from taktik.core.social_media.instagram.actions.core.base_action import BaseAction
from taktik.core.social_media.instagram.auth.login.credentials import CredentialsMixin
from taktik.core.social_media.instagram.auth.signup.signup import InstagramSignup
from taktik.core.social_media.instagram.ui.selectors.shell.auth import AUTH_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.text_input import TEXT_INPUT_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS as CC,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.story_viewer import STORY_SELECTORS
from taktik.core.social_media.instagram.workflows.cold_dm.sender import ColdDMSenderMixin
from taktik.core.social_media.instagram.workflows.management.notifications import (
    notifications_workflow as nw,
)
from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow

TEXT = "Test TAKTIK"
FIELD_BOUNDS = (40, 1500, 1040, 1600)


class _Quiet:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _Exists:
    """uiautomator2's `exists`: truthy, and callable with a timeout."""

    def __init__(self, value):
        self._value = value

    def __bool__(self):
        return self._value

    def __call__(self, timeout=None):
        return self._value


class _Rect:
    def __init__(self, bounds):
        self.left, self.top, self.right, self.bottom = bounds


class _Node:
    """The text field, or a button, as uiautomator2 hands it over."""

    def __init__(self, phone, bounds, on_tap, is_field=False, set_text_works=True):
        self._phone = phone
        self._bounds = bounds
        self._on_tap = on_tap
        self._is_field = is_field
        self._set_text_works = set_text_works
        self.exists = _Exists(True)
        self.count = 1

    @property
    def info(self):
        left, top, right, bottom = self._bounds
        return {"text": self._phone.field if self._is_field else "",
                "focused": self._is_field and self._phone.focused,
                "bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

    def bounds(self):
        return _Rect(self._bounds)

    def get(self, timeout=None):
        return self

    def click(self):
        self._on_tap()

    def get_text(self):
        return self._phone.field if self._is_field else ""

    def set_text(self, text):
        if not self._set_text_works:
            raise RuntimeError("set_text refused")
        self._phone.set_texts.append(text)
        self._phone.field = text


class _Absent:
    exists = _Exists(False)
    count = 0

    @property
    def info(self):
        raise RuntimeError("UiObjectNotFoundError")

    def get(self, timeout=None):
        raise RuntimeError("XPathElementNotFoundError")

    def click(self):
        raise RuntimeError("UiObjectNotFoundError")


class FoldingFieldPhone:
    """One text field; switching keyboards unfocuses it, and only a tap focuses it again.

    `steps` records, in order, each keyboard switch ("switch") and each tap that focuses the
    field ("tap"). Buttons are pressed without entering `steps`, unless pressing one focuses
    the field (a Reply that opens the composer with its "@name " prefilled).
    """

    device_id = serial = "PIXEL-6A"

    def __init__(self, fields=(), buttons=()):
        self.keyboard = kb.GBOARD_IME
        self.focused = False
        self.field = ""
        self.steps = []
        self.set_texts = []
        self.presses = []
        self.sent = []
        self._fields = list(fields)
        self._buttons = []
        for index, (selector, then) in enumerate(buttons):
            self.add_button(selector, then, index)

    def add_button(self, selector, then=None, index=None):
        index = len(self._buttons) if index is None else index
        bounds = (40, 100 + 120 * index, 1040, 200 + 120 * index)

        def press():
            self.presses.append(selector)
            if then:
                then()

        self._buttons.append((selector, _Node(self, bounds, press)))
        return bounds

    def field_node(self, set_text_works=True):
        return _Node(self, FIELD_BOUNDS, self.tap, is_field=True, set_text_works=set_text_works)

    def tap(self):
        self.steps.append("tap")
        self.focused = True
        return True

    def focus_with(self, prefill=""):
        """What a Reply does: the composer comes up focused, holding the mention."""
        def then():
            self.field = prefill
            self.tap()
        return then

    def shell(self, device_id, command):
        if "default_input_method" in command:
            return self.keyboard
        if command.startswith("ime set "):
            self.keyboard = command[len("ime set "):]
            self.steps.append("switch")
            self.focused = False
            return f"Input method {self.keyboard} selected for user #0"
        if self.keyboard == kb.TAKTIK_KEYBOARD_IME and self.focused:
            if kb.IME_MESSAGE_B64 in command:
                b64 = command.split("--es msg ", 1)[1].split(" ", 1)[0]
                self.field += base64.b64decode(b64).decode("utf-8")
            elif kb.IME_CLEAR_TEXT in command:
                self.field = ""
        if command.startswith("am broadcast"):
            return "Broadcast completed: result=0"
        return ""

    def _node(self, selector):
        if selector in self._fields:
            return self.field_node()
        for known, node in self._buttons:
            if known == selector:
                return node
        return _Absent()

    def xpath(self, selector):
        return self._node(selector)

    def __call__(self, **selector):
        if selector.get("focused"):
            return self.field_node() if self.focused else _Absent()
        if selector == {"className": DM_SELECTORS.edit_text_class_name}:
            return self.field_node()
        return self._node(selector)

    def _at(self, x, y):
        nodes = [self.field_node()] + [node for _, node in self._buttons]
        for node in nodes:
            left, top, right, bottom = node._bounds
            if left <= x <= right and top <= y <= bottom:
                return node
        return None

    def click(self, x, y):
        node = self._at(x, y)
        if node is not None:
            node.click()

    def human_tap(self, bounds, **_kw):
        x, y = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
        self.click(x, y)
        return (x, y)

    def press(self, _key):
        return True

    def send_keys(self, *_a, **_k):
        return None


@pytest.fixture
def phone(monkeypatch):
    phone = FoldingFieldPhone()
    monkeypatch.setattr(adb, "_run_adb_shell", phone.shell)
    monkeypatch.setattr(kb, "_active_ime_cache", {})
    monkeypatch.setattr(kb.time, "sleep", lambda *_: None)
    monkeypatch.setattr(typing_plan, "build_typing_plan", lambda text, rng=None: [("type", text)])
    return phone


def _typed_by_the_keyboard(phone, expected):
    """The field holds the text, typed by the Taktik Keyboard (not written by `set_text`)."""
    return phone.field == expected and phone.set_texts == []


def _find_and_click(phone):
    def find_and_click(selectors, timeout=5.0, human_delay=True):
        for selector in [selectors] if isinstance(selectors, str) else selectors:
            node = phone.xpath(selector)
            if node.exists:
                node.click()
                return True
        return False
    return find_and_click


def _action(cls, phone):
    """An action object on the fake phone, without the facade its __init__ would build."""
    action = cls.__new__(cls)
    action.device = phone
    action.logger = _Quiet()
    action._get_device_serial = lambda: phone.device_id
    action._human_like_delay = lambda *_a, **_k: None
    action._find_and_click = _find_and_click(phone)
    action.utils = types.SimpleNamespace(generate_human_like_delay=lambda *_a: 0)
    return action


# -- The DM composer atomic (messaging workflow, DM replies) --------------------------------------

def test_the_dm_composer_is_tapped_after_the_keyboard_switch(phone):
    """Switched after the tap, the message never reached the composer: `set_text` wrote it."""
    assert dm_composer.type_message(phone, None, TEXT) is True

    assert phone.steps == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, TEXT)


# -- The DM bridges, which tap the composer themselves before the atomic -------------------------

def _dm_bridge(phone):
    class _Dm(DMSenderMixin):
        device = phone
        device_id = phone.device_id

        def _verify_message_sent(self, message, attempts=4, delay=0.8):
            return True

    phone.add_button({"resourceId": DM_SELECTORS.send_button_resource_ids[0]})
    return _Dm()


def _cold_dm_bridge(phone):
    class _ColdDm(ColdDMSenderMixin):
        device = phone
        _keyboard = KeyboardService(phone.device_id)

    phone._fields.append({"resourceId": DM_SELECTORS.composer_edittext_resource_id})
    phone.add_button({"resourceId": DM_SELECTORS.send_button_resource_ids[0]})
    return _ColdDm()


@pytest.mark.parametrize("bridge", [_dm_bridge, _cold_dm_bridge], ids=["dm", "cold_dm"])
def test_the_dm_bridges_tap_the_composer_after_the_keyboard_switch(phone, bridge):
    """Their own tap came first, the switch after it: the composer folded before the atomic."""
    assert bridge(phone).send_message(TEXT) is True

    assert phone.steps[0] == "switch" and phone.steps.count("switch") == 1
    assert _typed_by_the_keyboard(phone, TEXT)


# -- The search fields ---------------------------------------------------------------------------

def _profile_search(phone):
    phone._fields += NAVIGATION_SELECTORS.explore_search_bar
    for selector in NAVIGATION_SELECTORS.search_result_selectors_for_username("ana"):
        phone.add_button(selector)
    nav = _action(SearchNavigationMixin, phone)
    nav.navigate_to_search = lambda: True
    nav._wait_for_element = lambda *_a, **_k: True
    nav._verify_profile_navigation = lambda _username: True
    return nav._navigate_via_search("ana"), "ana"


def _hashtag_search(phone):
    phone._fields += DETECTION_SELECTORS.hashtag_search_bar_selectors
    for selector in NAVIGATION_SELECTORS.hashtag_result_selectors("paris"):
        phone.add_button(selector)
    nav = _action(SearchNavigationMixin, phone)
    nav.navigate_to_search = lambda: True
    nav.detection_selectors = DETECTION_SELECTORS
    return nav.navigate_to_hashtag("paris"), "#paris"


def _content_hashtag_search(phone):
    phone._fields += DETECTION_SELECTORS.hashtag_search_bar_selectors
    for selector in CC.hashtag_result_selectors("paris"):
        phone.add_button(selector)
    business = _action(BaseAction, phone)
    business.nav_actions = types.SimpleNamespace(navigate_to_search=lambda: True)
    business.detection_selectors = DETECTION_SELECTORS
    return content_navigation.navigate_to_hashtag(business, "paris"), "#paris"


@pytest.mark.parametrize("search", [
    _profile_search, _hashtag_search, _content_hashtag_search,
], ids=["profile", "hashtag", "content_hashtag"])
def test_the_search_fields_are_tapped_after_the_keyboard_switch(phone, search):
    """Switched after the tap, the query never reached the search field."""
    reached, query = search(phone)

    assert reached is True
    assert phone.steps == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, query)


# -- The comment composer ------------------------------------------------------------------------

def _comment_action(phone):
    phone._fields += POST_COMMENTS_SELECTORS.comment_field_selectors
    comment = _action(CommentAction, phone)
    comment.post_selectors = POST_COMMENTS_SELECTORS
    return comment


def test_the_comment_field_is_tapped_after_the_keyboard_switch(phone):
    assert _comment_action(phone)._type_comment(TEXT) is True

    assert phone.steps == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, TEXT)


def test_a_threaded_reply_switches_before_its_reply_opens_the_composer(phone, monkeypatch):
    """The Reply tap is what focuses the composer (with "@name " in it): switched after it, the
    composer folded before the bot's own tap on it."""
    comment = _comment_action(phone)
    reply_bounds = phone.add_button("reply", phone.focus_with("@ana "))
    comment.default_config = {"comment_delay_range": (0, 0)}
    comment._is_comments_view_open = lambda: True
    comment._find_comment_reply_control = lambda _handle: reply_bounds
    comment._post_comment = lambda: True
    comment._record_posted_comment = lambda *_a, **_k: 1
    comment._close_comment_popup = lambda: True

    result = comment.reply_to_comment_in_thread("ana", TEXT)

    assert result["success"] is True
    assert phone.steps[0] == "switch" and phone.steps.count("switch") == 1
    assert _typed_by_the_keyboard(phone, "@ana " + TEXT)


# -- The reply from the notifications ------------------------------------------------------------

def _notifications(phone):
    workflow = nw.NotificationsEngagementWorkflow.__new__(nw.NotificationsEngagementWorkflow)
    workflow.device = phone
    workflow.device_id = phone.device_id
    workflow.logger = _Quiet()
    return workflow


def test_the_notification_reply_composer_is_tapped_after_the_keyboard_switch(phone):
    assert _notifications(phone)._type_into(phone.field_node(), TEXT) is True

    assert phone.steps == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, TEXT)


def test_a_notification_reply_switches_before_its_reply_opens_the_composer(phone):
    phone._fields += POST_COMMENTS_SELECTORS.comment_composer_indicators

    def send():
        phone.sent.append(phone.field)
        phone.field = ""

    phone.add_button(POST_COMMENTS_SELECTORS.post_comment_button_xpaths[0], send)
    workflow = _notifications(phone)
    workflow.comment_selectors = POST_COMMENTS_SELECTORS
    workflow.ensure_notifications_screen = lambda: True
    workflow._optimize_locale = lambda: None
    workflow._notify = lambda *_a, **_k: None
    workflow._open_reply_thread = lambda _username: phone.focus_with("@ana ")() or True
    workflow._return_to_notifications = lambda *_a, **_k: True

    result = workflow.reply_to_comment("ana", TEXT)

    assert result["success"] is True
    assert phone.steps[0] == "switch" and phone.steps.count("switch") == 1
    assert phone.sent == ["@ana " + TEXT] and phone.set_texts == []


# -- Fields typed through TextActions after the caller's own tap ---------------------------------

def _text_actions(phone):
    return _action(TextActions, phone)


def _signup_field(phone):
    phone._fields += AUTH_SELECTORS.signup_phone_field
    signup = _action(InstagramSignup, phone)
    signup.text_actions = _text_actions(phone)
    return signup._fill_field(AUTH_SELECTORS.signup_phone_field, "0612345678", "Phone"), "0612345678"


def _login_password(phone):
    login = _action(CredentialsMixin, phone)
    login.auth_selectors = AUTH_SELECTORS
    login.text_actions = _text_actions(phone)
    field = phone.field_node(set_text_works=False)
    return login._clear_and_fill_field(field, "s3cret", "password"), "s3cret"


def _post_caption(phone):
    phone._fields += CC.composer_xpaths()
    phone.add_button(CC.caption_confirm_xpaths()[0])
    workflow = InstagramPostWorkflow.__new__(InstagramPostWorkflow)
    workflow._log = lambda *_a, **_k: None
    workflow._a = {"kb": _text_actions(phone), "click": _action(BaseAction, phone)}
    return workflow._fill_caption(TEXT), TEXT


def _story_reply(phone):
    story = _action(StoryInteractionMixin, phone)
    phone._fields.append(STORY_SELECTORS.story_message_composer)
    if not story.open_story_reply_composer():
        return False, TEXT
    return _text_actions(phone).type_text(TEXT), TEXT


def _text_actions_field(phone):
    phone._fields += TEXT_INPUT_SELECTORS.comment_field_selectors
    kb_actions = _text_actions(phone)
    return kb_actions._type_in_field(TEXT, TEXT_INPUT_SELECTORS.comment_field_selectors, "comment"), TEXT


@pytest.mark.parametrize("fill", [
    _signup_field, _login_password, _post_caption, _story_reply, _text_actions_field,
], ids=["signup", "login_password", "post_caption", "story_reply", "text_actions_field"])
def test_the_fields_typed_after_their_own_tap_are_tapped_after_the_switch(phone, fill):
    """TextActions and the raw keyboard type into whatever is focused: switched after the
    caller's tap, the text went nowhere and the typing still said it had worked."""
    filled, text = fill(phone)

    assert filled is True
    assert phone.steps == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, text)


def test_the_login_username_is_tapped_again_after_the_switch(phone):
    """Its first taps reveal the clear button; the tap the typing relies on comes last."""
    login = _action(CredentialsMixin, phone)
    login.auth_selectors = AUTH_SELECTORS
    login.text_actions = _text_actions(phone)

    assert login._clear_username_and_fill(phone.field_node(set_text_works=False), "ana") is True

    assert phone.steps[-2:] == ["switch", "tap"]
    assert _typed_by_the_keyboard(phone, "ana")
