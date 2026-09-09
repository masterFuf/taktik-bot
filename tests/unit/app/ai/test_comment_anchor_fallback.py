"""Which of the two comments gets published is decided HERE, in code — never by the model.

Measured on 2026-09-09: offering the generic register to the model as an equal option makes it
take that option by default (bland answers 5 -> 10 of 18, average length 97 -> 63 characters).
So the model writes both and states its anchor; this module verifies the claim and picks.
"""

from taktik.core.app.ai.providers.openrouter import AIService

VISION = "A wet cobblestone square at night, reflets sur les paves"
CAPTION = "Sous la chaleur de la pluie"


def answer(**fields):
    import json
    base = {"reasoning": "r", "comment": "c", "safe_comment": "s", "anchor": ""}
    base.update(fields)
    return json.dumps(base, ensure_ascii=False)


def generate(payload, **kwargs):
    service = AIService(api_key="x" * 10)
    service._call_openrouter = lambda model, messages, *a, **k: {
        "success": True, "model": model, "cost_usd": 0.0, "text": payload,
    }
    return service.generate_smart_comment(
        post_description=VISION, username="x", post_caption=CAPTION, language="fr", **kwargs
    )


def test_a_verified_anchor_publishes_the_specific_comment():
    result = generate(answer(anchor="les reflets sur les paves",
                             comment="Ces reflets sur les paves sont dingues"))

    assert result["anchor_ok"] is True
    assert result["used_safe_comment"] is False
    assert result["comment"] == "Ces reflets sur les paves sont dingues"


def test_an_unverifiable_anchor_publishes_the_safe_comment():
    """The invention never reaches the thread, and nothing is dropped: a comment is still posted."""
    result = generate(answer(anchor="des cakes",
                             comment="J adore l idee de l integrer dans des cakes",
                             safe_comment="Cette lumiere est superbe"))

    assert result["anchor_ok"] is False
    assert result["used_safe_comment"] is True
    assert result["comment"] == "Cette lumiere est superbe"


def test_without_a_fallback_the_comment_stands_rather_than_the_run_breaking():
    """A truncated or half-formed answer is the provider's known failure, not a reason to post
    nothing — the anchor verdict is still reported so the case stays countable."""
    result = generate(answer(anchor="des cakes", comment="Un commentaire", safe_comment=""))

    assert result["anchor_ok"] is False and result["used_safe_comment"] is False
    assert result["comment"] == "Un commentaire"


def test_a_non_json_answer_keeps_the_prior_behaviour():
    """The oldest fallback in this function still wins: raw text becomes the comment."""
    result = generate("Juste un commentaire brut")

    assert result["comment"] == "Juste un commentaire brut"
    assert result["anchor"] == "" and result["anchor_ok"] is False


def test_a_declined_post_is_not_rescued_by_the_fallback():
    """`should_comment: false` means DO NOT COMMENT. Publishing the safe comment there would
    turn a deliberate refusal into a post, which is worse than the invention it guards against.
    """
    result = generate(
        answer(anchor="des cakes", comment="", safe_comment="Joli", should_comment=False),
        require_relevance_decision=True,
    )

    assert result["should_comment"] is False
    assert result["comment"] == "" and result["used_safe_comment"] is False
