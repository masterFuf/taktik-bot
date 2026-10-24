"""A DM reply Instagram shows waiting to be sent is neither sent nor failed: it is pending.

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
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.sender as sender_module
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.dm.message_extraction import DMMessageExtractionMixin
from taktik.core.social_media.instagram.workflows.dm.sender import DMSenderMixin, ReplyOutcome
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
    wait_timeout = 0.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def __call__(self, resourceId=None, **_selector):
        return _Selection([n for n in etree.fromstring(self.xml.encode("utf-8")).iter("node")
                           if n.get("resource-id") == resourceId])


class _Conversation(DMSenderMixin, DMMessageExtractionMixin):
    """The DM runtime as far as the verification of a send reads it: the Pixel 6 Pro's width."""

    screen_width = 1440

    def __init__(self, xml):
        self.device = _Phone(xml)


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    monkeypatch.setattr(sender_module.time, "sleep", lambda *_: None)
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
