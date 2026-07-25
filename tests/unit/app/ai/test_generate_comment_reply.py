"""Replying to a comment is riskier than commenting on a post.

A comment on a post lands on a wall. A reply lands ON somebody, in their thread, and the two
ways to get it wrong are: publishing something that answers nothing (which is what makes an
account read as automated), and publishing raw model output.
"""

import pytest

from taktik.core.app.ai.providers.openrouter import AIService, _COMMENT_WRITING_RULES


def _service(response_text, success=True):
    svc = AIService.__new__(AIService)
    svc.model_generation = "google/gemini-3-flash-preview"
    svc.ipc = None
    svc.captured = {}

    def _completion(system, user, **kwargs):
        svc.captured = {"system": system, "user": user, **kwargs}
        if not success:
            return {"success": False, "error": "provider down"}
        return {"success": True, "text": response_text, "model": "m", "cost_usd": 0.0001}

    svc.text_completion = _completion
    return svc


APPROVED = '{"should_reply": true, "reasoning": "answers their question", "comment": "oui carrement"}'
REFUSED = '{"should_reply": false, "reasoning": "emoji only", "comment": ""}'


# ── What gets published ─────────────────────────────────────────────────────

def test_an_approved_reply_comes_back_ready_to_post():
    out = _service(APPROVED).generate_comment_reply("Ca marche en 1 mois ?", "dianeou38")
    assert out["should_reply"] is True
    assert out["comment"] == "oui carrement"
    assert out["reasoning"] == "answers their question"


def test_a_comment_worth_nothing_is_refused_and_carries_no_text():
    out = _service(REFUSED).generate_comment_reply("🔥🔥", "dianeou38")
    assert out["should_reply"] is False
    assert out["comment"] == ""


@pytest.mark.parametrize("raw", [
    "Sure! Here's a reply: nice one",   # prose, no JSON
    '{"comment": "nice one"}',          # JSON without the decision
    '{"should_reply": true}',           # decision without a reply
    '{"should_reply": "yes", "comment": "nice one"}',  # decision not a real boolean
    "",
])
def test_an_unparseable_answer_publishes_nothing(raw):
    """Fail CLOSED: raw model output under someone's comment is worse than silence."""
    out = _service(raw).generate_comment_reply("Ca marche ?", "dianeou38")
    assert out["should_reply"] is False
    assert out["comment"] == ""


def test_an_empty_comment_is_refused_before_any_call():
    svc = _service(APPROVED)
    out = svc.generate_comment_reply("   ", "dianeou38")
    assert out["success"] is False
    assert svc.captured == {}  # no tokens spent


def test_a_provider_failure_is_reported_not_swallowed():
    out = _service(APPROVED, success=False).generate_comment_reply("Ca marche ?", "dianeou38")
    assert out["success"] is False


# ── The prompt ──────────────────────────────────────────────────────────────

def test_the_benchmark_writing_rules_reach_the_reply_prompt():
    """These rules were validated with Kevin and then left behind once already — the sparkle
    tic reached production because they lived in the benchmark and not in the prompt."""
    svc = _service(APPROVED)
    svc.generate_comment_reply("Ca marche ?", "dianeou38")
    system = svc.captured["system"]
    assert "{_COMMENT_WRITING_RULES}" not in system  # interpolated, not literal
    for rule_line in _COMMENT_WRITING_RULES.splitlines():
        assert rule_line in system


def test_the_reply_is_grounded_in_what_the_person_actually_wrote():
    svc = _service(APPROVED)
    svc.generate_comment_reply("Ca marche en 1 mois ?", "dianeou38", post_caption="Notre methode")
    assert "Ca marche en 1 mois ?" in svc.captured["user"]
    assert "Notre methode" in svc.captured["user"]


def test_our_account_voice_is_carried_into_the_reply():
    svc = _service(APPROVED)
    svc.generate_comment_reply(
        "Ca marche ?", "dianeou38",
        account_persona={"displayName": "Institut Rentable", "niche": "business coaching",
                         "tonePersonality": "direct", "objective": "vendre du coaching"},
    )
    system = svc.captured["system"]
    assert "Institut Rentable" in system
    assert "business coaching" in system
    assert "direct" in system


def test_an_explicit_language_overrides_matching_theirs():
    svc = _service(APPROVED)
    svc.generate_comment_reply("Does it work?", "dianeou38", language="fr")
    assert "Write in French" in svc.captured["system"]


def test_auto_language_follows_the_person_being_answered():
    svc = _service(APPROVED)
    svc.generate_comment_reply("Ca marche ?", "dianeou38", language="auto")
    assert "same language as their comment" in svc.captured["system"]


def test_the_generation_model_is_used_not_the_analysis_one():
    svc = _service(APPROVED)
    svc.generate_comment_reply("Ca marche ?", "dianeou38")
    assert svc.captured["model"] == "google/gemini-3-flash-preview"
    assert "generate_comment_reply" in svc.captured["label"]
