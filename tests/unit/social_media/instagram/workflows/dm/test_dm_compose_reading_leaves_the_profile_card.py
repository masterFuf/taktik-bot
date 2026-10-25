"""The reading of a 447 conversation leaves out the partner's card at the top of the thread.

In 447 the conversation is a Compose list (`message_list`): a message is a bare TextView of its row.
The card Instagram shows above the first message (the partner's photo, name, handle, « 92 followers ·
0 publications », « Vous suit », « Vous suivez ... et 3 autres », the « Voir le profil » button) is
made of the same bare TextViews, in its own row. The one bubble reader (`_collect_messages`, which
`dm_read` and the context of an AI reply receive) took its lines for messages: our own ones by their
left edge past the quarter of the screen, « Vous suivez ... » as a message received, the one an AI
reply would have answered on a conversation that holds none.

The card is the row of `message_list` that holds the « Voir le profil » button (`igds_button`, a bare
Compose id); a bubble's row never does on these captures. The screens are real dumps of a Pixel 6a
(Instagram 447, French), anonymized: a conversation with the card and one message of ours
(`ig447_fr_dm_conversation_composer.xml`), a new professional conversation that shows only the card
(`ig447_fr_dm_new_professional_conversation.xml`), and a conversation scrolled to its top, the card
then one message (`ig447_fr_dm_thread.xml`).
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.message_extraction as message_extraction
from taktik.core.social_media.instagram.workflows.dm.conversation_payload import build_conversation_payload
from taktik.core.social_media.instagram.workflows.dm.reply_check import ConversationBubbles
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
WITH_ONE_MESSAGE = (FIXTURES / "ig447_fr_dm_conversation_composer.xml").read_text(encoding="utf-8")
CARD_ONLY = (FIXTURES / "ig447_fr_dm_new_professional_conversation.xml").read_text(encoding="utf-8")
THREAD_TOP = (FIXTURES / "ig447_fr_dm_thread.xml").read_text(encoding="utf-8")

#: The lines of the card on these captures, as the anonymiser named them.
CARD_LINES = {"name_11 name_12", "user_1", "92 followers · 0 publications", "132 followers · 2 publications",
              "Vous suit"}
OUR_MESSAGE = ("name_16 name_5 name_17 abonnement ! name_18 de name_19 name_20 name_21 name_22, name_23 "
               "name_24 pas si tu as name_25 name_26.")
THREAD_MESSAGE = "name_4, name_5 message de name_6 depuis le name_7, name_8 name_9 name_10 name_11"


class _Selection:
    """`d(resourceId=...)` and `d(className=...)` as the bubble reader asks them."""

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
    """The Pixel 6a showing one capture; a scroll changes nothing (the top of the thread is shown)."""

    wait_timeout = 0.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def window_size(self):
        return 1080, 2400

    def __call__(self, resourceId=None, className=None, **_selector):
        return _Selection([n for n in etree.fromstring(self.xml.encode("utf-8")).iter("node")
                           if (resourceId is None or n.get("resource-id") == resourceId)
                           and (className is None or n.get("class") == className)])


@pytest.fixture
def ig_447():
    """The selectors as a phone on 447 gets them at connect; the baseline put back after."""
    from taktik.core.compat.selectors.setup import INSTAGRAM_TARGET_VERSION, apply_version_overrides

    apply_version_overrides("instagram", "447.0.0.55.81")
    yield
    apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)


@pytest.fixture(autouse=True)
def _no_scroll(monkeypatch):
    monkeypatch.setattr(message_extraction, "human_scroll_raw", lambda *_a, **_k: None)
    monkeypatch.setattr(message_extraction, "time", SimpleNamespace(sleep=lambda *_a: None))


def _read(xml):
    return ConversationBubbles(_Phone(xml))._collect_messages()


def test_the_captures_hold_the_card_lines_as_bare_texts_of_the_list():
    """What the test stands on: the card's lines are bare TextViews of `message_list`."""
    for xml in (WITH_ONE_MESSAGE, CARD_ONLY, THREAD_TOP):
        root = etree.fromstring(xml.encode("utf-8"))
        bare = {n.get("text") for n in root.xpath(
            '//*[@resource-id="com.instagram.android:id/message_list"]//node'
            '[@class="android.widget.TextView"][@resource-id=""]')}
        assert bare & CARD_LINES


def test_a_conversation_reads_its_message_and_not_the_card(ig_447):
    messages = _read(WITH_ONE_MESSAGE)

    assert [m["text"] for m in messages] == [OUR_MESSAGE]
    assert messages[0]["is_sent"] is True


def test_a_conversation_that_shows_only_the_card_holds_no_message(ig_447):
    """« Vous suivez ... et 3 autres » was read as a message received: an AI reply would answer it."""
    messages = _read(CARD_ONLY)

    assert messages == []
    payload = build_conversation_payload(real_username="user_1", inbox_username="user_1", messages=messages,
                                         is_group=False, can_reply=True)
    assert payload["messages"] == []


def test_a_thread_read_to_its_top_starts_with_its_first_message(ig_447):
    assert [m["text"] for m in _read(THREAD_TOP)] == [THREAD_MESSAGE]
