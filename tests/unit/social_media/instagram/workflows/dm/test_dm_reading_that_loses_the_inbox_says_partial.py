"""A reading that loses the inbox after a scroll says it read a part of the list (`partial`).

It returned what it had read, as a success, and only its log said the inbox was gone (« The DM
inbox is no longer on screen: reading stopped after N conversation(s) »): the app could not tell
it from a whole reading (question 3 of the report `boitevide`, 2026-10-26). It stays a success on
what was read, and its result says `partial: true`.

The screens are real captures: the 447 inbox (`ig447_fr_dm_inbox_pills_no_ids.xml`), and after the
scroll a conversation (`ig410_fr_dm_thread_pixel6pro.xml`), a screen that is no inbox.
"""

import taktik.core.social_media.instagram.workflows.dm.agent_handler as agent_handler
from test_dm_reading_of_the_447_inbox import CONVERSATION, _a_447_phone, _Phone, _Runtime  # noqa: F401 (fixture)


class _LosingPhone(_Phone):
    """The inbox; its first scroll leaves it for a conversation."""

    def swipe_points(self, *_a, **_k):
        self.start = CONVERSATION
        self.screen = CONVERSATION


def test_an_inbox_lost_after_a_scroll_is_a_partial_success():
    result = agent_handler._read(_Runtime(_LosingPhone()), 0, None)

    assert result["success"] is True and result["total"] > 0
    assert result["partial"] is True


def test_a_reading_that_keeps_its_inbox_is_whole():
    result = agent_handler._read(_Runtime(_Phone()), 3, None)

    assert result["success"] is True and result["partial"] is False
