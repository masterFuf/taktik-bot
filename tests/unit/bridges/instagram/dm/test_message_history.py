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

    def __init__(self, total: int = 0, screen_size: int = 8, step: int = 5, full: list | None = None):
        self._full = full if full is not None else [_msg(i) for i in range(total)]
        self._screen_size = screen_size
        self._step = step
        self._start = max(0, len(self._full) - screen_size)

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


def test_identical_text_messages_are_not_lost():
    # Repeated identical texts (e.g. "ok" twice) must survive: a per-message dedup would
    # conflate them; sequence-overlap matching keeps them distinct.
    full = [
        {"type": "text", "text": "ok", "is_sent": False},
        {"type": "text", "text": "B", "is_sent": True},
        {"type": "text", "text": "ok", "is_sent": False},
        {"type": "text", "text": "C", "is_sent": True},
    ]
    convo = FakeConversation(full=full, screen_size=3, step=2)

    messages = convo._collect_messages(max_messages=50, max_scrolls=10)

    assert [(m["text"], m["is_sent"]) for m in messages] == [
        ("ok", False), ("B", True), ("ok", False), ("C", True),
    ]


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


# ── Per-message timestamp capture (C1) ───────────────────────────────────────


class _FakeElement:
    def __init__(self, text: str, bounds: dict):
        self._text = text
        self._bounds = bounds

    def get_text(self) -> str:
        return self._text

    @property
    def info(self) -> dict:
        return {"bounds": self._bounds}


class _FakeQuery:
    def __init__(self, elements: list):
        self._elements = elements

    @property
    def count(self) -> int:
        return len(self._elements)

    def __getitem__(self, index: int):
        return self._elements[index]


class _SeparatorConversation(DMMessageExtractionMixin):
    """Drives only the timestamp helpers with a faked TextView query + screen width."""

    def __init__(self, elements: list, screen_width: int = 1080):
        self._elements = elements
        self.screen_width = screen_width

    def device(self, className: str | None = None):
        return _FakeQuery(self._elements)


def test_separator_detection_keeps_only_full_width_clock_headers():
    elements = [
        _FakeElement("Jun 12, 10:29 AM", {"left": 0, "right": 1080, "top": 100}),   # header -> kept
        _FakeElement("see you at 10:30", {"left": 60, "right": 600, "top": 200}),    # message bubble -> excluded
        _FakeElement("Active now", {"left": 0, "right": 1080, "top": 50}),           # no clock -> excluded
    ]
    convo = _SeparatorConversation(elements)

    seps = convo._collect_timestamp_separators()

    assert [s["label"] for s in seps] == ["Jun 12, 10:29 AM"]


def test_attach_timestamps_tags_each_message_with_nearest_header_above():
    convo = _SeparatorConversation([])
    convo._collect_timestamp_separators = lambda: [  # type: ignore[method-assign]
        {"top": 100, "label": "12 juin, 10:29"},
        {"top": 500, "label": "10:45"},
    ]
    items = [{"top": 120, "text": "a"}, {"top": 480, "text": "b"}, {"top": 600, "text": "c"}]

    convo._attach_timestamps(items)

    assert items[0]["timestamp"] == "12 juin, 10:29"
    assert items[1]["timestamp"] == "12 juin, 10:29"  # 480 is still below the 10:45 header
    assert items[2]["timestamp"] == "10:45"


def test_attach_timestamps_leaves_messages_above_the_first_header_untagged():
    convo = _SeparatorConversation([])
    convo._collect_timestamp_separators = lambda: [{"top": 300, "label": "10:45"}]  # type: ignore[method-assign]
    items = [{"top": 100, "text": "a"}]

    convo._attach_timestamps(items)

    assert "timestamp" not in items[0]
