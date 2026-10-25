"""A DM thread read from the inbox is filed under the partner's handle, not the name shown.

Measured on a Pixel 6 Pro (Instagram 410, French, 2026-10-24), CLI `dm_read`: the conversation with
an account that has a display name was recorded with `dm_threads.partner_username` = that name
(« prénom nom »), not the handle. The reader took the conversation header's title, which is the
display name when there is one; the handle is the header's subtitle, under it.

The screens are real dumps, anonymized: the inbox laid out with pills of that phone
(`ig410_fr_dm_inbox_pills.xml`) and a conversation of that phone whose header shows the display name
then the handle (`ig410_fr_dm_conversation_named_partner.xml`); the conversation of an account with
no display name, the handle as its title (`ig410_fr_dm_thread_pixel6pro.xml`). A tap on an inbox row
opens the conversation of the test; what the reading collects in it (the bubbles, the reply state)
has its own tests and is a stand-in here.
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.reader as reader_module
from taktik.core.social_media.instagram.workflows.dm.conversation_payload import conversation_partner
from taktik.core.social_media.instagram.workflows.dm.reader import DMConversationReaderMixin
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
INBOX = (FIXTURES / "ig410_fr_dm_inbox_pills.xml").read_text(encoding="utf-8")
NAMED = (FIXTURES / "ig410_fr_dm_conversation_named_partner.xml").read_text(encoding="utf-8")
HANDLE_ONLY = (FIXTURES / "ig410_fr_dm_thread_pixel6pro.xml").read_text(encoding="utf-8")
EN_NEW_CONVERSATION = (FIXTURES / "ig410_en_dm_thread_new_conversation.xml").read_text(encoding="utf-8")


def _node_text(xml, resource_id, attribute):
    node = next(n for n in etree.fromstring(xml.encode("utf-8")).iter("node")
                if n.get("resource-id") == f"{PKG}:id/{resource_id}")
    return node.get(attribute)


class _Selection:
    def __init__(self, phone, resource_id):
        self._phone = phone
        self._resource_id = resource_id

    def _nodes(self):
        tree = etree.fromstring(self._phone.dump_hierarchy().encode("utf-8"))
        return [n for n in tree.iter("node") if n.get("resource-id") == self._resource_id]

    def exists(self, timeout=0):
        return bool(self._nodes())

    def get_text(self):
        nodes = self._nodes()
        return nodes[0].get("text") if nodes else None

    def click(self):
        # Only the conversation's back arrow is clicked this way.
        self._phone.press("back")


class _Phone:
    """The inbox, then the conversation a tap on a row opens; Back returns to the inbox."""

    wait_timeout = 0.0
    info = {"displayWidth": 1440, "displayHeight": 3120}

    def __init__(self, conversation):
        self.conversation = conversation
        self.screen = INBOX
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": PKG}

    def __call__(self, resourceId=None, **_selector):
        return _Selection(self, resourceId)

    def click(self, _x, _y):
        if self.screen is INBOX:
            self.screen = self.conversation

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key, *_a):
        if key == "back":
            self.screen = INBOX


class _Reader(DMConversationReaderMixin):
    """The DM runtime as far as the inbox reading reads it; the conversation's content is a
    stand-in (its own tests)."""

    screen_width = 1440

    def __init__(self, phone):
        self.device = phone
        self.events = []

    def _emit_dm_event(self, event, flush=False):
        self.events.append(event)

    def _resolve_thread_username(self, thread_info, fallback):
        return fallback

    def _detect_conversation_reply_state(self, real_username):
        return False, True

    def _collect_messages(self, *_a, **_k):
        return [{"text": "bonjour", "is_sent": False, "type": "text"}]

    def _is_accounts_to_follow_visible(self):
        return False


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(reader_module, "time", SimpleNamespace(sleep=lambda *_: None))
    import taktik.core.social_media.instagram.workflows.dm.conversation_state as state
    monkeypatch.setattr(state, "time", SimpleNamespace(sleep=lambda *_: None))


def test_the_thread_of_a_partner_with_a_display_name_is_filed_under_the_handle():
    handle = _node_text(NAMED, "header_subtitle", "content-desc")
    shown_name = _node_text(NAMED, "header_title", "text")
    assert handle != shown_name

    conversations = _Reader(_Phone(NAMED)).read_conversations(1)

    assert [c["username"] for c in conversations] == [handle]


def test_the_thread_of_a_partner_without_display_name_keeps_the_title():
    handle = _node_text(HANDLE_ONLY, "header_title", "text")

    conversations = _Reader(_Phone(HANDLE_ONLY)).read_conversations(1)

    assert [c["username"] for c in conversations] == [handle]


def test_the_header_reading():
    assert conversation_partner(NAMED) == (_node_text(NAMED, "header_title", "text"),
                                           _node_text(NAMED, "header_subtitle", "content-desc"))
    # A subtitle that is no handle (two words) gives none: the title, shaped like a handle, is it.
    title = _node_text(EN_NEW_CONVERSATION, "header_title", "text").strip()
    assert " " in _node_text(EN_NEW_CONVERSATION, "header_subtitle", "content-desc")
    assert conversation_partner(EN_NEW_CONVERSATION) == (title, title.lower())
    assert conversation_partner(INBOX) == (None, None)


def test_off_the_inbox_nothing_is_read_and_no_empty_inbox_is_claimed():
    # Lab `dm.list_unread` on a conversation (Pixel 6 Pro, 410 in English, 2026-10-24): « No threads
    # found », then « 0 conversation(s) read » as a success. The screen is that conversation.
    phone = _Phone(NAMED)
    phone.screen = (FIXTURES / "ig410_en_dm_conversation_no_tab_bar.xml").read_text(encoding="utf-8")

    not_read = _Reader(phone).read_conversations(5)

    assert getattr(not_read, "error_code", None) == "DM_INBOX_NOT_SHOWN", not_read
