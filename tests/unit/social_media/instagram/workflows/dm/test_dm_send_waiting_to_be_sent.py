"""A DM Instagram shows waiting to be sent is neither sent nor failed: it is pending.

Measured on a Pixel 6 Pro (Instagram 410, French, 2026-10-24), CLI `dm_send` with the network cut
while the reply was typed: Send tapped, the reply's bubble in the conversation with an icon at its
side described « Envoi… ». The reply was declared « Send not confirmed: message did not appear in the
conversation » (exit 1): the icon shifts the bubble to the left, where it read as a received one. Less
than 10 s after the network came back, the icon was gone and the message had left. A caller that
tried again would have sent it twice.

The screens are real dumps of that phone, anonymized with one mapping: the conversation with the
bubble waiting (`ig410_fr_dm_reply_pending_send.xml`) and the same conversation once it was sent
(`ig410_fr_dm_reply_sent_after_network.xml`). In English, the same phone and the same run, the icon
says « Sending… » (`ig410_en_dm_reply_pending_send.xml`): the conversation holds the replies already
gone above it, and only the last one, ours, carries the icon.

The same screens hold the three sends to one check (`reply_check.reply_outcome`): the inbox reply
(`dm_send`), the welcome DM and the cold DM, which pressed Send and counted the message as sent
without reading the conversation.
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.reply_check as reply_check_module
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.dm.message_extraction import DMMessageExtractionMixin
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome
from taktik.core.social_media.instagram.workflows.dm.sender import DMSenderMixin
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
PENDING = (FIXTURES / "ig410_fr_dm_reply_pending_send.xml").read_text(encoding="utf-8")
SENT = (FIXTURES / "ig410_fr_dm_reply_sent_after_network.xml").read_text(encoding="utf-8")
PENDING_EN = (FIXTURES / "ig410_en_dm_reply_pending_send.xml").read_text(encoding="utf-8")


def _last_bubble_text(xml):
    nodes = [n for n in etree.fromstring(xml.encode("utf-8")).iter("node")
             if n.get("resource-id") == f"{PKG}:id/direct_text_message_text_view"]
    return max(nodes, key=lambda n: int(n.get("bounds").split("][")[0].split(",")[1])).get("text")


class _Selection:
    """`d(resourceId=...)` as the bubble reader asks it: count, items, bounds, text."""

    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def count(self):
        return len(self._nodes)

    @property
    def exists(self):
        return bool(self._nodes)

    def __getitem__(self, index):
        return _Selection([self._nodes[index]])

    @property
    def info(self):
        left_top, right_bottom = self._nodes[0].get("bounds")[1:-1].split("][")
        left, top = (int(v) for v in left_top.split(","))
        right, bottom = (int(v) for v in right_bottom.split(","))
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

    def get_text(self):
        return self._nodes[0].get("text")


class _Phone:
    """The Pixel 6 Pro showing one capture: its dump, its xpath, `d(resourceId=...)` and
    `d(description=...)` (exact, as uiautomator2 matches them), its size."""

    wait_timeout = 0.0
    info = {"displayWidth": 1440, "displayHeight": 3120}

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def __call__(self, resourceId=None, description=None, **_selector):
        return _Selection([n for n in etree.fromstring(self.xml.encode("utf-8")).iter("node")
                           if (resourceId is None or n.get("resource-id") == resourceId)
                           and (description is None or n.get("content-desc") == description)])


class _Conversation(DMSenderMixin, DMMessageExtractionMixin):
    """The DM runtime as far as the verification of a send reads it: the Pixel 6 Pro's width."""

    screen_width = 1440

    def __init__(self, xml):
        self.device = _Phone(xml)


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    monkeypatch.setattr(reply_check_module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _in(language):
    set_active_locale(language)


def test_the_captures_show_the_same_reply():
    assert _last_bubble_text(PENDING) == _last_bubble_text(SENT)


@pytest.mark.parametrize("language, xml", [("fr", PENDING), ("en", PENDING_EN)], ids=["fr", "en"])
def test_a_reply_waiting_to_be_sent_is_pending_not_absent(language, xml):
    _in(language)
    reply = _last_bubble_text(xml)

    assert _Conversation(xml)._verify_message_sent(reply) is ReplyOutcome.PENDING


def test_the_replies_already_gone_above_it_are_sent():
    # The English conversation: the reply before ours, without the icon, read as a reply sent.
    _in("en")
    nodes = [n for n in etree.fromstring(PENDING_EN.encode("utf-8")).iter("node")
             if n.get("resource-id") == f"{PKG}:id/direct_text_message_text_view"]
    assert len(nodes) >= 2
    from taktik.core.social_media.instagram.workflows.dm.conversation_payload import pending_send_texts

    assert pending_send_texts(PENDING_EN) == [_last_bubble_text(PENDING_EN)]


def test_the_same_reply_once_the_network_is_back_is_sent():
    reply = _last_bubble_text(SENT)

    assert _Conversation(SENT)._verify_message_sent(reply) is ReplyOutcome.SENT


def test_another_text_is_not_taken_for_the_reply_waiting():
    assert _Conversation(PENDING)._verify_message_sent("une autre réponse, jamais tapée") is ReplyOutcome.NOT_SENT


# -- The Send button, the one of every DM send ----------------------------------------------------

@pytest.mark.parametrize("language, xml", [("fr", PENDING), ("en", PENDING_EN)], ids=["fr", "en"])
def test_the_icon_of_a_message_waiting_is_never_taken_for_the_send_button(language, xml):
    # The composer is empty after Send: no button on these screens. In English the icon says
    # « Sending… », which a `contains(@content-desc, "Send")` took for the button.
    _in(language)

    assert dm_composer.find_send_button(_Phone(xml)) is None


# -- The welcome DM and the cold DM: the same check after Send ------------------------------------

@pytest.fixture
def composer_pressed(monkeypatch):
    """The composer found, the message typed, Send pressed: what is left is the conversation the
    phone shows afterwards, the capture."""
    monkeypatch.setattr(dm_composer, "find_message_input", lambda device, **_k: object())
    monkeypatch.setattr(dm_composer, "type_message", lambda *_a, **_k: True)
    monkeypatch.setattr(dm_composer, "click_send_button", lambda device, **_k: True)


def _messaging(xml):
    from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness

    return MessagingBusiness(_Phone(xml))


@pytest.mark.parametrize("language, xml", [("fr", PENDING), ("en", PENDING_EN)], ids=["fr", "en"])
def test_a_dm_sent_from_a_profile_waiting_to_be_sent_is_pending(composer_pressed, language, xml):
    # `send_in_open_conversation`, the welcome DM's and the cold DM's sending.
    _in(language)
    message = _last_bubble_text(xml)

    assert _messaging(xml).send_in_open_conversation(message, typos=False) is ReplyOutcome.PENDING


def test_a_dm_sent_from_a_profile_once_the_network_is_back_is_sent(composer_pressed):
    message = _last_bubble_text(SENT)

    assert _messaging(SENT).send_in_open_conversation(message, typos=False) is ReplyOutcome.SENT


def test_a_dm_sent_from_a_profile_that_never_showed_is_not_sent(composer_pressed):
    assert _messaging(SENT).send_in_open_conversation("un message jamais tapé", typos=False) \
        is ReplyOutcome.NOT_SENT


@pytest.fixture
def welcome_road(monkeypatch, composer_pressed):
    """The welcome DM's road (`send_welcome_dm` -> `send_dm`): the walk to the profile and the
    conversation opened, the look for a block, home; the conversation is the capture's."""
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
    from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness

    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr(NavigationActions, "navigate_to_profile", lambda self, username, **_: True)
    monkeypatch.setattr(NavigationActions, "navigate_to_home", lambda self: True)
    monkeypatch.setattr(MessagingBusiness, "open_conversation_from_profile", lambda self, username=None: True)
    monkeypatch.setattr(ProblematicPageDetector, "is_action_blocked", lambda self: False)


@pytest.mark.parametrize("language, xml", [("fr", PENDING), ("en", PENDING_EN)], ids=["fr", "en"])
def test_a_welcome_dm_waiting_to_be_sent_is_reported_pending_not_sent(welcome_road, language, xml):
    from taktik.core.social_media.instagram.workflows.notifications.welcome_dm import send_welcome_dm

    _in(language)
    result = send_welcome_dm(_Phone(xml), "newbie", _last_bubble_text(xml))

    assert result["success"] is False and result["pending"] is True
    assert result["error_code"] == "DM_SEND_PENDING"


def test_a_welcome_dm_the_conversation_shows_sent_is_sent(welcome_road):
    from taktik.core.social_media.instagram.workflows.notifications.welcome_dm import send_welcome_dm

    result = send_welcome_dm(_Phone(SENT), "newbie", _last_bubble_text(SENT))

    assert result == {"success": True, "message": "welcome DM sent to @newbie"}


@pytest.mark.parametrize("language, xml", [("fr", PENDING), ("en", PENDING_EN)], ids=["fr", "en"])
def test_a_cold_dm_waiting_to_be_sent_is_pending_not_sent(composer_pressed, monkeypatch, language, xml):
    from taktik.core.social_media.instagram.workflows.cold_dm import sender as cold_dm_sender
    from taktik.core.social_media.instagram.workflows.cold_dm.navigation import ColdDMNavigationMixin
    from taktik.core.social_media.instagram.workflows.cold_dm.sender import ColdDMSenderMixin

    class _ColdDm(ColdDMSenderMixin, ColdDMNavigationMixin):
        def __init__(self, phone):
            self.device = phone
            self.device_manager = phone

    monkeypatch.setattr(cold_dm_sender.time, "sleep", lambda *_: None)
    _in(language)

    assert _ColdDm(_Phone(xml)).send_message(_last_bubble_text(xml)) is ReplyOutcome.PENDING


# -- Instagram 447: the Compose thread ------------------------------------------------------------
#
# Pixel 6a (Instagram 447, French, 2026-10-25), CLI coldDm with the network cut a second after
# « Sending message... »: the run said « DM sent and confirmed in the conversation », `dms_sent: 1`,
# while the conversation showed the bubble with its « Envoi… » icon; it left once, when the network
# came back. In 447 the thread is Compose: a bubble is a bare TextView in its row of `message_list`,
# the icon a bare ImageView of the same row; none of the ids of 410 (`message_content`,
# `action_icon`) is there. The two screens of that run, anonymized together: waiting
# (`ig447_fr_dm_compose_bubble_pending_send.xml`) and the same bubble once sent
# (`ig447_fr_dm_compose_bubble_sent_after_network.xml`). Every bubble of this conversation is ours.

PENDING_447 = (FIXTURES / "ig447_fr_dm_compose_bubble_pending_send.xml").read_text(encoding="utf-8")
SENT_447 = (FIXTURES / "ig447_fr_dm_compose_bubble_sent_after_network.xml").read_text(encoding="utf-8")


class _Phone447(_Phone):
    """The Pixel 6a."""

    info = {"displayWidth": 1080, "displayHeight": 2400}


@pytest.fixture
def ig_447():
    """The selectors as a phone on 447 gets them at connect; the baseline put back after."""
    from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version

    apply_version_overrides("instagram", "447.0.0.55.81")
    yield
    apply_version_overrides("instagram", baseline_version("instagram"))


def _compose_bubbles(xml):
    """The bubbles of the Compose thread, top first: the bare TextViews of `message_list` that
    are no date, no reaction chip and no line of the partner's card above the messages."""
    root = etree.fromstring(xml.encode("utf-8"))
    message_list = [node for node in root.iter("node") if node.get("resource-id") == f"{PKG}:id/message_list"][0]
    rows = [row for row in message_list if row.get("class") == "com.facebook.compose.view.MetaComposeView"
            and not any(node.get("resource-id") == "igds_button" for node in row.iter("node"))]
    return [node.get("text") for row in rows for node in row.iter("node")
            if node.get("class") == "android.widget.TextView" and not node.get("resource-id")
            and node.get("text") not in (None, "", "❤")]


def test_the_447_captures_show_the_same_bubble_last():
    assert _compose_bubbles(PENDING_447)[-1] == _compose_bubbles(SENT_447)[-1]


def test_a_447_bubble_waiting_to_be_sent_is_pending(ig_447):
    from taktik.core.social_media.instagram.workflows.dm.reply_check import ConversationBubbles, reply_outcome

    phone = _Phone447(PENDING_447)
    message = _compose_bubbles(PENDING_447)[-1]

    assert reply_outcome(phone, message, ConversationBubbles(phone)._collect_text_messages) \
        is ReplyOutcome.PENDING


def test_only_the_447_bubble_with_the_icon_is_waiting(ig_447):
    from taktik.core.social_media.instagram.workflows.dm.conversation_payload import pending_send_texts

    assert pending_send_texts(PENDING_447) == [_compose_bubbles(PENDING_447)[-1]]
    assert pending_send_texts(SENT_447) == []


def test_the_same_447_bubble_once_the_network_is_back_is_sent(ig_447):
    from taktik.core.social_media.instagram.workflows.dm.reply_check import ConversationBubbles, reply_outcome

    phone = _Phone447(SENT_447)

    assert reply_outcome(phone, _compose_bubbles(SENT_447)[-1],
                         ConversationBubbles(phone)._collect_text_messages) is ReplyOutcome.SENT


def test_our_newest_447_bubble_is_read_as_ours_waiting_or_sent(ig_447):
    # « Our » bubble is the bottom-most one, and ours by its left edge (a bubble of the other person
    # hugs the left edge): the icon shifts the waiting one 42 px to the left, still past the line.
    from taktik.core.social_media.instagram.workflows.dm.reply_check import ConversationBubbles

    for xml in (PENDING_447, SENT_447):
        bubbles = ConversationBubbles(_Phone447(xml))._collect_text_messages()
        newest = max(bubbles, key=lambda bubble: bubble["top"])
        assert newest["text"] == _compose_bubbles(xml)[-1] and newest["is_sent"] is True


def test_a_447_cold_dm_waiting_to_be_sent_is_pending_not_sent(ig_447, composer_pressed, monkeypatch):
    # The run of the capture, by its own road: `send_message` -> `send_in_open_conversation`.
    from taktik.core.social_media.instagram.workflows.cold_dm import sender as cold_dm_sender
    from taktik.core.social_media.instagram.workflows.cold_dm.navigation import ColdDMNavigationMixin
    from taktik.core.social_media.instagram.workflows.cold_dm.sender import ColdDMSenderMixin

    class _ColdDm(ColdDMSenderMixin, ColdDMNavigationMixin):
        def __init__(self, phone):
            self.device = phone
            self.device_manager = phone

    monkeypatch.setattr(cold_dm_sender.time, "sleep", lambda *_: None)

    assert _ColdDm(_Phone447(PENDING_447)).send_message(_compose_bubbles(PENDING_447)[-1]) \
        is ReplyOutcome.PENDING
    assert _ColdDm(_Phone447(SENT_447)).send_message(_compose_bubbles(SENT_447)[-1]) is ReplyOutcome.SENT


def test_the_410_form_stays_read_on_447(ig_447):
    # The override holds both forms: a 447 serving the thread of 410 still shows its waiting bubble.
    from taktik.core.social_media.instagram.workflows.dm.conversation_payload import pending_send_texts

    assert pending_send_texts(PENDING) == [_last_bubble_text(PENDING)]
