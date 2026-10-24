"""The reading of the 447 inbox: the main conversations first, then only the rows whole on screen.

Replayed on a Pixel 6a (Instagram 447, French, 2026-10-24), CLI `dm_read`:
- the « Principal » pill was tapped only after the reading, by the reset that follows it: the
  conversations were read from « Tout ». The reading now puts it on display before the first row;
- the last row of the screen ran under the tab bar (its bounds end 170 px below the thread list): the
  tap meant for it landed on the tab bar's search tab, « Could not open conversation with ... », then
  « No threads found » on a screen that was no longer the inbox. Only the rows whole inside the thread
  list are read; the cut one comes whole after a scroll.

- the message requests screen of 447 lists its rows the old way (`row_inbox_container`), which the 447
  row selector (Compose rows) did not see: a reading of the requests would have found none. Under its
  rows, « Invitations masquées » (a row without digest) and « Tout supprimer », never to be tapped.

The screens are that inbox and the requests screen opened from it, anonymized
(`ig447_fr_dm_inbox_pills_no_ids.xml`, `ig447_fr_dm_requests_folder.xml`), with the selectors a 447
phone gets at connect (version overrides). A tap on a row opens a conversation of the session
(`ig410_fr_dm_thread_pixel6pro.xml`, its title a handle); Back returns. What the reading collects in
it has its own tests and is a stand-in here.
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.agent_handler as agent_handler
import taktik.core.social_media.instagram.workflows.dm.conversation_state as conversation_state
import taktik.core.social_media.instagram.workflows.dm.inbox_reset as inbox_reset
import taktik.core.social_media.instagram.workflows.dm.reader as reader_module
from taktik.core.compat.selectors.setup import INSTAGRAM_TARGET_VERSION, apply_version_overrides
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.dm.inbox_reset import DMInboxResetMixin
from taktik.core.social_media.instagram.workflows.dm.reader import DMConversationReaderMixin
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
INBOX = (FIXTURES / "ig447_fr_dm_inbox_pills_no_ids.xml").read_text(encoding="utf-8")
CONVERSATION = (FIXTURES / "ig410_fr_dm_thread_pixel6pro.xml").read_text(encoding="utf-8")
REQUESTS = (FIXTURES / "ig447_fr_dm_requests_folder.xml").read_text(encoding="utf-8")
#: Never to be tapped on the requests screen: « Tout supprimer », and the hidden requests' row.
DELETE_ALL = (42, 2174, 1027, 2290)
HIDDEN_REQUESTS_ROW = (0, 1233, 1080, 1416)
REQUEST_ROWS = ((0, 636, 1021, 835), (0, 835, 585, 1034), (0, 1034, 652, 1233))
#: The clickable node of the « Principal » pill, and the bottom of the thread list (the tab bar under it).
PRINCIPAL_PILL = (237, 862, 471, 988)
THREAD_LIST_BOTTOM = 2211


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
        self._phone.press("back")


class _Phone:
    """The 447 inbox; a tap on it opens the conversation, Back returns; drags change nothing."""

    wait_timeout = 0.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, start=INBOX):
        self.start = start
        self.screen = start
        self.clicks = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": PKG}

    def __call__(self, resourceId=None, **_selector):
        return _Selection(self, resourceId)

    def click(self, x, y):
        self.clicks.append((self.screen is self.start, x, y))
        if self.screen is self.start and y > PRINCIPAL_PILL[3]:
            self.screen = CONVERSATION

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def swipe_points(self, *_a, **_k):
        pass

    def press(self, key, *_a):
        if key == "back":
            self.screen = self.start


class _Runtime(DMInboxResetMixin, DMConversationReaderMixin):
    """The DM runtime as far as a reading of the inbox goes; the conversation's content is a stand-in."""

    screen_width = 1080

    def __init__(self, phone):
        self.device = phone
        self.events = []

    def restart_instagram(self):
        return True

    def navigate_to_dm_inbox(self):
        return True

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

    def _reset_inbox_to_top(self, strategy="auto"):
        return None


@pytest.fixture(autouse=True)
def _a_447_phone(monkeypatch):
    no_wait = SimpleNamespace(sleep=lambda *_: None)
    for module in (reader_module, conversation_state, inbox_reset, agent_handler):
        monkeypatch.setattr(module, "time", no_wait)
    # The base and the language are not this test's: nothing is written, nothing detected.
    monkeypatch.setattr(agent_handler, "_detect_app_language", lambda runtime: None)
    monkeypatch.setattr(agent_handler, "account_id_from_inbox_header", lambda runtime: None)
    monkeypatch.setattr(agent_handler, "resolve_account_id", lambda runtime: None)
    monkeypatch.setattr(agent_handler, "record_conversations", lambda account_id, conversations: None)
    set_active_locale("fr")
    apply_version_overrides("instagram", "447.0.0.55.81")
    yield
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)
    set_active_locale(None)


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def test_the_main_conversations_are_put_on_display_before_the_first_row():
    phone = _Phone()

    result = agent_handler._read(_Runtime(phone), 3, None)

    assert result["success"] is True
    on_inbox, x, y = phone.clicks[0]
    assert on_inbox and _inside((x, y), PRINCIPAL_PILL), f"first tap {phone.clicks[0]}: not the « Principal » pill"
    assert len(phone.clicks) > 1, "no row read after the pill"


def test_a_row_cut_by_the_bottom_of_the_thread_list_is_never_tapped():
    phone = _Phone()

    conversations = _Runtime(phone).read_conversations(0)

    taps_on_the_inbox = [(x, y) for on_inbox, x, y in phone.clicks if on_inbox]
    assert taps_on_the_inbox, "no row tapped"
    assert all(y < THREAD_LIST_BOTTOM for _x, y in taps_on_the_inbox), f"a tap under the list: {taps_on_the_inbox}"
    assert conversations is not None


def test_the_requests_of_447_are_read_and_nothing_else_is_tapped():
    phone = _Phone(start=REQUESTS)

    _Runtime(phone).read_conversations(0)

    taps = [(x, y) for on_requests, x, y in phone.clicks if on_requests]
    # Each of the three requests is opened (the stand-in opens one conversation for all three, which
    # the reading takes for one conversation seen again: what is read in it is not this test's).
    tapped_rows = {row for row in REQUEST_ROWS for tap in taps if _inside(tap, row)}
    assert tapped_rows == set(REQUEST_ROWS), taps
    assert not any(_inside(tap, DELETE_ALL) for tap in taps), f"« Tout supprimer » tapped: {taps}"
    assert not any(_inside(tap, HIDDEN_REQUESTS_ROW) for tap in taps), f"hidden requests opened: {taps}"
