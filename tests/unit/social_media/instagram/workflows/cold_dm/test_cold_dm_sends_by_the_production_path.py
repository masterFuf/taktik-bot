"""The cold DM sends as the welcome DM does: one way to send a DM from a profile.

The cold DM had its own sending next to the production one (`MessagingBusiness.send_dm_from_profile`,
the welcome DM's, reached through `send_dm`): its own lookups of the composer and the send button by
`d(resourceId=...)`, its own detection of a request already sent, and its own way home (a Back,
then the home tab by id, description, then description fragments). It now opens the conversation
by `MessagingBusiness.open_conversation_from_profile`, sends by `send_in_open_conversation` (without
typos, after the time a human takes to type), and goes home by the production `navigate_to_home`.

The profile is a real screen (`ig410_en_profile_with_message_button.xml`, Instagram 410 in English,
anonymized): the tap on its header's Message button is the production opener's, read through
uiautomator2's engine behind the clone proxy and the facade; it opens a new conversation
(`ig410_en_dm_thread_new_conversation.xml`), which the opener waits for. The conversation has no
capture with a message typed (the send button appears only then): the sending is recorded at its seam; its
composer and send button are the shared composer's (`actions/atomic/text/dm_composer.py`), tested
there.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.instagram.workflows.cold_dm.sender as cold_dm_sender
import taktik.core.social_media.instagram.workflows.cold_dm.workflow as workflow_module
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.cold_dm.recipient_policy import ColdDmRecipientPolicy
from taktik.core.social_media.instagram.workflows.cold_dm.workflow import SENT, ColdDMWorkflow
from taktik.core.social_media.instagram.workflows.dm import messaging
from taktik.core.social_media.instagram.workflows.dm.messaging import INVITE_ALREADY_SENT, MessagingBusiness
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome

from test_cold_dm_reads_only_a_profile import CONVERSATION_EN, MESSAGE_BUTTON, PROFILE_EN, _Phone, _workflow


@pytest.fixture
def sending(monkeypatch):
    """What the production sending in an open conversation is asked, and what it answers."""
    asked = []
    answer = {"value": ReplyOutcome.SENT}

    def send_in_open_conversation(self, message, *, typos=True):
        asked.append((type(self).__name__, message, typos))
        return answer["value"]

    monkeypatch.setattr(MessagingBusiness, "send_in_open_conversation", send_in_open_conversation)
    opener = MessagingBusiness.open_conversation_from_profile
    opened = []

    def open_conversation_from_profile(self, username=None):
        opened.append(type(self).__name__)
        return opener(self, username)

    monkeypatch.setattr(MessagingBusiness, "open_conversation_from_profile", open_conversation_from_profile)
    monkeypatch.setattr(messaging.time, "sleep", lambda *_: None)
    monkeypatch.setattr(cold_dm_sender.time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield SimpleNamespace(asked=asked, answer=answer, opened=opened)
    set_active_locale(None)


def test_the_cold_dm_opens_the_conversation_and_sends_by_the_production_sending(monkeypatch, sending):
    phone = _Phone(PROFILE_EN, message_button_opens=CONVERSATION_EN)
    monkeypatch.setattr(ColdDMWorkflow, "open_recipient_profile", lambda self, username: True)
    monkeypatch.setattr(workflow_module, "look_for_action_block", lambda *a, **k: False)

    reached = _workflow(phone).reach_and_send("demo_recipient", lambda: "Hello there", ColdDmRecipientPolicy())

    assert reached["outcome"] == SENT and reached["send_result"] is ReplyOutcome.SENT
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    left, top, right, bottom = MESSAGE_BUTTON
    assert left <= x <= right and top <= y <= bottom
    assert sending.opened == ["MessagingBusiness"]
    assert sending.asked == [("MessagingBusiness", "Hello there", False)]


def test_a_request_already_sent_reaches_the_cold_dm_as_such(sending):
    sending.answer["value"] = INVITE_ALREADY_SENT

    assert _workflow(_Phone(PROFILE_EN)).send_message("Hello there") == INVITE_ALREADY_SENT


def test_the_welcome_dm_sends_by_the_same_function_with_its_typos(monkeypatch, sending):
    phone = _Phone(PROFILE_EN, message_button_opens=CONVERSATION_EN)
    monkeypatch.setattr(messaging, "look_for_action_block", lambda *a, **k: False)

    assert messaging.send_dm(SimpleNamespace(device=phone), "demo_recipient", "Welcome!",
                             navigate_to_profile=False) is ReplyOutcome.SENT

    assert len(phone.taps) == 1
    assert sending.opened == ["MessagingBusiness"]
    assert sending.asked == [("MessagingBusiness", "Welcome!", True)]


def test_a_request_already_sent_is_no_welcome_dm_sent(monkeypatch, sending):
    """`send_dm` answers what the DM came to: a request already waiting is not a DM sent."""
    sending.answer["value"] = INVITE_ALREADY_SENT
    monkeypatch.setattr(messaging, "look_for_action_block", lambda *a, **k: False)

    assert messaging.send_dm(SimpleNamespace(device=_Phone(PROFILE_EN)), "demo_recipient", "Welcome!",
                             navigate_to_profile=False) is ReplyOutcome.NOT_SENT


def test_the_cold_dm_goes_home_by_the_production_navigation(monkeypatch):
    homes = []
    monkeypatch.setattr(NavigationActions, "navigate_to_home", lambda self: homes.append(type(self).__name__) or True)

    assert _workflow(_Phone(PROFILE_EN)).go_home() is True
    assert homes == ["NavigationActions"]
