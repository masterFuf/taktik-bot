"""Writing-style transfer block for smart comments.

`_build_style_block` turns the operated account's own writing samples (organic comment
replies / DMs, injected by the desktop app on the persona) into a few-shot voice-imitation
block. It must stay a no-op when absent/garbage so the open-source bot works standalone.
"""

from taktik.core.app.ai.comments.generation import _build_style_block


def test_empty_when_absent_or_garbage():
    assert _build_style_block("acme", None) == ""
    assert _build_style_block("acme", "not a list") == ""
    assert _build_style_block("acme", []) == ""
    assert _build_style_block("acme", [1, 2, {"x": 1}]) == ""   # no usable strings
    assert _build_style_block("acme", ["  ", "a"]) == ""        # blank + too short (<3)


def test_includes_samples_and_account_name():
    block = _build_style_block("Sample", ["trop stylé ce spot 🔥", "grave j'adore"])
    assert "Sample" in block
    assert "trop stylé ce spot 🔥" in block
    assert "grave j'adore" in block
    # Frames it as style-only imitation, not content reuse
    assert "STYLE" in block
    assert "never reuse" in block


def test_dedup_case_insensitive_and_whitespace_collapsed():
    block = _build_style_block("acme", ["Hello there", "hello   there", "HELLO THERE"])
    # collapsed + deduped to a single bullet
    assert block.count('- "') == 1
    assert '- "Hello there"' in block


def test_caps_number_of_samples():
    samples = [f"sample number {i} here" for i in range(50)]
    block = _build_style_block("acme", samples, max_samples=5)
    assert block.count('- "') == 5


def test_drops_overlong_samples():
    long_one = "x" * 500
    block = _build_style_block("acme", ["short and sweet", long_one], max_len=240)
    assert "short and sweet" in block
    assert long_one not in block
