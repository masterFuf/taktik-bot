"""Unit tests for bounded DM conversation history capture (scroll-up assembly).

The real capture scrolls the device; here we drive the assembly logic by faking the
per-screen capture + the scroll, so we can assert ordering, de-duplication and bounding
without a device.
"""

from bridges.instagram.engagement.runtime.dm.message_extraction import DMMessageExtractionMixin


def _msg(idx: int) -> dict:
    """A received text message labelled by its chronological index."""
    return {"type": "text", "text": f"m{idx}", "is_sent": idx % 2 == 1}


class FakeConversation(DMMessageExtractionMixin):
    """Simulates a chat: full history oldest->newest, a viewport that starts at the
    bottom (newest) and moves up by ``step`` on each scroll, with overlap."""

    def __init__(self, total: int, screen_size: int = 8, step: int = 5):
        self._full = [_msg(i) for i in range(total)]
        self._screen_size = screen_size
        self._step = step
        self._start = max(0, total - screen_size)

    def _collect_current_screen(self) -> list[dict]:
        return list(self._full[self._start : self._start + self._screen_size])

    def _scroll_to_older_messages(self) -> None:
        self._start = max(0, self._start - self._step)


def test_short_conversation_returns_all_in_order():
    convo = FakeConversation(total=3)

    messages = convo._collect_messages()

    assert [m["text"] for m in messages] == ["m0", "m1", "m2"]
    # Last item stays the newest (last_message_is_ours depends on this).
    assert messages[-1]["text"] == "m2"


def test_long_conversation_is_bounded_to_most_recent_and_ordered():
    convo = FakeConversation(total=30)

    messages = convo._collect_messages(max_messages=20, max_scrolls=4)

    # Bounded to the most recent 20, chronological, newest last.
    assert len(messages) == 20
    assert messages[0]["text"] == "m10"
    assert messages[-1]["text"] == "m29"
    texts = [m["text"] for m in messages]
    assert texts == [f"m{i}" for i in range(10, 30)]


def test_overlap_across_screens_is_deduplicated():
    convo = FakeConversation(total=12, screen_size=6, step=3)

    messages = convo._collect_messages(max_messages=50, max_scrolls=10)

    texts = [m["text"] for m in messages]
    # No duplicates despite overlapping viewports, full history recovered in order.
    assert texts == [f"m{i}" for i in range(12)]
    assert len(texts) == len(set(texts))


def test_stops_scrolling_when_no_new_messages_appear():
    convo = FakeConversation(total=4, screen_size=8, step=5)
    calls = {"scrolls": 0}
    original_scroll = convo._scroll_to_older_messages

    def counting_scroll():
        calls["scrolls"] += 1
        original_scroll()

    convo._scroll_to_older_messages = counting_scroll

    messages = convo._collect_messages(max_messages=20, max_scrolls=4)

    assert [m["text"] for m in messages] == ["m0", "m1", "m2", "m3"]
    # One probe scroll reveals nothing new -> we stop instead of scrolling max times.
    assert calls["scrolls"] == 1
