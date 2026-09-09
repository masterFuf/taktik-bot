"""Grammatical gender was classified, stored, and never handed to the writer.

92 % of our comments are French, where nearly every adjective and past participle agrees. A
writer that knows neither who it addresses nor who it speaks AS has to guess, and half those
guesses are wrong — publicly, under someone else's post. Measured on the 2026-09-09 replays:
"j'étais curieux" written as a female persona, on an account whose gender is stored nowhere.

Two sides, two different fixes. THEIRS is `profile_qualification.ai_gender`, filled for 84 % of
profiles and simply never plumbed through — so the prompt now states it. OURS is stored nowhere,
so the only honest instruction is to forbid the forms that would require it.
"""

from taktik.core.app.ai.comments.generation import _agreement_self, _agreement_target
from taktik.core.app.ai.providers.openrouter import AIService


def prompts(**kwargs):
    """The two halves of the system message actually sent, as (cached prefix, per-call rest).

    Returned separately rather than joined because WHICH SIDE a rule lands on is part of the
    contract: anything naming the profile being written to belongs after the breakpoint, or
    every profile gets its own cache entry and the prefix is never read back.
    """
    seen = {}
    service = AIService(api_key="x" * 10)

    def capture(model, messages, *a, **k):
        blocks = messages[0]["content"] if messages else []
        if isinstance(blocks, str):
            blocks = [{"text": blocks, "cache_control": {}}]
        seen["stable"] = "".join(b["text"] for b in blocks if b.get("cache_control"))
        seen["variable"] = "".join(b["text"] for b in blocks if not b.get("cache_control"))
        return {"success": True, "model": model, "cost_usd": 0.0,
                "text": '{"anchor": "a", "comment": "c", "safe_comment": "s", "reasoning": "r"}'}

    service._call_openrouter = capture
    service.generate_smart_comment(post_description="a photo", username="x", language="fr",
                                   **kwargs)
    return seen["stable"], seen["variable"]


def test_our_own_gender_is_never_guessed():
    """The rule holds whatever we know about the other side, because it is about US."""
    for gender in ("female", "male", "brand", "", "unknown"):
        block = _agreement_self() + _agreement_target(gender)
        assert "you do not know your own account's gender" in block, gender


def test_a_known_target_gender_reaches_the_prompt():
    """The whole point: the classification is 84 % filled and used to stop at the database."""
    assert "WOMAN" in prompts(target_gender="female")[1]
    assert "MAN" in prompts(target_gender="male")[1]


def test_each_half_of_the_rule_lands_on_the_right_side_of_the_breakpoint():
    """The cached prefix pays for itself only if it is byte-identical between two profiles.

    Our own agreement rule never changes, so it leads and is billed at a tenth. The target's
    gender changes with every profile: in the prefix it would give each one its own cache entry
    and cancel the saving that made this split worth doing (674 -> 183 uSD, measured).
    """
    stable, variable = prompts(target_gender="female")

    assert "you do not know your own account's gender" in stable
    assert "WOMAN" not in stable
    assert "WOMAN" in variable

    other, _ = prompts(target_gender="male")
    assert other == stable, "the prefix must not move when the profile does"


def test_a_brand_is_not_addressed_as_a_person():
    """7 426 of the classified profiles are brands — "tu es superbe" to a moving company."""
    block = _agreement_target("brand")
    assert "BRAND" in block and "not an individual" in block
    assert "WOMAN" not in block and "MAN" not in block


def test_an_unknown_gender_asks_for_avoidance_not_a_coin_flip():
    """Silence would leave the model free to pick; 16 % of profiles have no classification."""
    for unknown in ("", "unknown", "   ", "wat"):
        block = _agreement_target(unknown)
        assert "their gender is unknown" in block, repr(unknown)
        assert "WOMAN" not in block and "MAN" not in block


def test_the_default_call_still_carries_the_rule():
    """Every caller that has not been updated yet must still get the self-agreement guard."""
    stable, variable = prompts()
    assert "you do not know your own account's gender" in stable
    assert "their gender is unknown" in variable


def test_the_reply_generator_gets_the_same_rule():
    """A reply is as French as a comment, and the rules block is shared on purpose — a rule
    proven on one generator must never be silently missing from the other."""
    seen = {}
    service = AIService(api_key="x" * 10)
    def capture(model, messages, *a, **k):
        blocks = messages[0]["content"]
        seen["system"] = blocks if isinstance(blocks, str) else "".join(
            block.get("text", "") for block in blocks
        )
        return {"success": True, "model": model, "cost_usd": 0.0,
                "text": '{"should_reply": true, "comment": "ok", "reasoning": "r"}'}

    service._call_openrouter = capture
    service.generate_comment_reply(comment_text="joli", username="x", language="fr",
                                   target_gender="female")

    assert "WOMAN" in seen["system"]
    assert "you do not know your own account's gender" in seen["system"]


def test_the_rule_offers_no_phrase_a_model_can_simply_copy():
    """A suggested replacement is read by a weak model as a phrase to use.

    Measured on 2026-09-09: with "ça m'intrigue" given as an example way out, mistral-nemo
    published that exact phrase in 5 of 18 comments — the anti-tic guard's whole problem,
    introduced by the rule meant to fix a different one. The rule now states the forbidden
    SHAPE and sends the model looking for its own way out.
    """
    for gender in ("female", "male", "brand", ""):
        block = _agreement_self() + _agreement_target(gender)
        for ready_made in ("ça m'intrigue", "ça m'a surpris", "trop envie de tester"):
            assert ready_made not in block, f"{gender}: {ready_made}"
        assert "do NOT reuse a phrase from these rules" in block
