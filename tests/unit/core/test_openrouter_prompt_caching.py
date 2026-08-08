"""The classification prefix must stay cacheable, and the cache must be shared across accounts.

Profile classification is ~97% of the AI bill, and its prompt carries the injected taxonomy
(~1.7k tokens) on every single call. Measured against production prompts on 2026-08-03,
implicit caching never fired once: every call paid full input price for a byte-identical
prefix. An explicit cache_control breakpoint cuts that prefix to a tenth of the price.

The saving is silent when it breaks — the run still works, it just costs ~1.6x more — so the
two things that would kill it are pinned here:
  - the taxonomy must sit BEFORE the breakpoint (otherwise nothing substantial is cached);
  - the app language and the per-account engagement block must sit AFTER it (otherwise each
    account and each language gets its own cache entry, and back-to-back profiles miss).
"""

from taktik.core.app.ai.providers.openrouter import AIService, cacheable_system


TAXONOMY = {
    "beauty_wellness": ["Hair & Nail Art", "Skincare & Cosmetics"],
    "art_design": ["Photography", "Tattoo & Body Art"],
}


def _captured_system_prompt(**kwargs):
    """Run classify_profile_niche with the network stubbed, return the system message sent."""
    service = AIService(api_key="test-key", niche_taxonomy=TAXONOMY)
    captured = {}

    def fake_vision_json_completion(system_prompt, user_prompt, image_path, **_):
        captured["system"] = system_prompt
        return {"success": True, "text": "{}", "payload": {"niche_category": "art_design"}}

    service.vision_json_completion = fake_vision_json_completion
    service._image_for_vision = lambda path: "data:image/jpeg;base64,AAAA"
    service.classify_profile_niche(username="someone", screenshot_path=__file__, **kwargs)
    return captured["system"]


def test_cacheable_system_marks_only_the_stable_block():
    blocks = cacheable_system("stable part", "variable part")
    assert blocks[0]["text"] == "stable part"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert blocks[1]["text"] == "variable part"
    assert "cache_control" not in blocks[1]


def test_cacheable_system_without_a_variable_part_sends_one_block():
    assert len(cacheable_system("stable only")) == 1


def test_taxonomy_is_inside_the_cached_prefix():
    blocks = _captured_system_prompt()
    assert isinstance(blocks, list), "system prompt must be block-shaped to carry a breakpoint"
    cached = blocks[0]
    assert cached["cache_control"] == {"type": "ephemeral"}
    # The expensive, repeated part: every sub-niche label must be in the cached block.
    for sub_niche in ("Hair & Nail Art", "Skincare & Cosmetics", "Photography"):
        assert sub_niche in cached["text"]


def test_language_and_engagement_stay_out_of_the_cached_prefix():
    blocks = _captured_system_prompt(
        response_language="fr",
        include_engagement=True,
        account_niche="beauty_wellness",
        account_sub_niche="Hair & Nail Art",
    )
    cached, variable = blocks[0]["text"], blocks[1]["text"]
    # Language belongs to the tail: caching it would fork the cache per app language.
    assert "French" in variable and "French" not in cached
    # Engagement relativity names the operated account — per-account, must not be cached.
    assert "ENGAGEMENT RELEVANCE" in variable and "ENGAGEMENT RELEVANCE" not in cached
    assert "beauty_wellness" in variable


def test_two_accounts_share_one_cached_prefix():
    """Different operated accounts must produce the SAME cached block, byte for byte."""
    first = _captured_system_prompt(
        response_language="fr", include_engagement=True, account_niche="beauty_wellness")
    second = _captured_system_prompt(
        response_language="en", include_engagement=True, account_niche="art_design")
    assert first[0]["text"] == second[0]["text"]
    assert first[1]["text"] != second[1]["text"]
