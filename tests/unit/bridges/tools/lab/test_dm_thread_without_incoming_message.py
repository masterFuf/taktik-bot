"""`dm.read_last_incoming` declares a thread that holds only our own messages, and only that.

The Lab reads the last message received in the open thread with the production reader
(`_collect_text_messages`). A conversation we opened and that nobody answered has none: on the
Pixel 6a (Instagram 447, French, Lab bench of October 2026) the thread with one of Kevin's accounts
held the partner's card and our first message, and the test failed (« no incoming message ») as if
the reader were broken. The reader read the thread: one bubble, ours. That is the account's data,
which the action declares (`details.not_applicable`), as a post without comments is. A thread the
reader got nothing from stays a failure: a broken reader is never taken for an unanswered thread.

The screens are real dumps, anonymized: on that phone, a conversation with the card and one message
of ours (`ig447_fr_dm_conversation_composer.xml`) and a new conversation that shows only the card
(`ig447_fr_dm_new_professional_conversation.xml`); a French thread of Instagram 410 whose last
message was received (`ig410_fr_dm_thread.xml`: no 447 capture holds a received message).
"""

from types import SimpleNamespace

import pytest

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions
from unit.paths import CORE
from unit.social_media.instagram.workflows.dm.test_dm_compose_reading_leaves_the_profile_card import _Phone

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


@pytest.fixture(autouse=True)
def _lab_actions():
    register_actions()


@pytest.fixture
def ig_447():
    """The selectors as a phone on 447 gets them at connect; the baseline put back after."""
    from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version

    apply_version_overrides("instagram", "447.0.0.55.81")
    yield
    apply_version_overrides("instagram", baseline_version("instagram"))


def _read_last_incoming(name):
    phone = _Phone((FIXTURES / name).read_text(encoding="utf-8"))
    return ACTION_REGISTRY["dm.read_last_incoming"](SimpleNamespace(device=phone), {})


def test_a_thread_with_only_our_message_is_declared(ig_447):
    result = _read_last_incoming("ig447_fr_dm_conversation_composer.xml")

    assert result["success"] is False
    assert result["details"]["not_applicable"] == "the open thread holds only our own messages"


def test_a_received_message_is_read_and_nothing_is_declared():
    result = _read_last_incoming("ig410_fr_dm_thread.xml")

    assert result["success"] is True
    assert "not_applicable" not in result["details"]


def test_a_thread_the_reader_got_nothing_from_stays_a_failure(ig_447):
    result = _read_last_incoming("ig447_fr_dm_new_professional_conversation.xml")

    assert result["success"] is False
    assert "not_applicable" not in (result.get("details") or {})
