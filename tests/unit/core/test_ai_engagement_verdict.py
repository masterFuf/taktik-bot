"""AI engagement verdict normalization (Lot 1 of the AI-relevance spec).

`AIService._normalize_engagement` must coerce whatever the model returns into a safe, typed
verdict — or None so callers cleanly fall back to the non-AI behaviour.
"""

from taktik.core.app.ai.providers.openrouter import AIService

norm = AIService._normalize_engagement


def test_none_when_missing_or_garbage():
    assert norm(None) is None
    assert norm("nope") is None
    assert norm(123) is None


def test_full_verdict_coerced_and_clamped():
    v = norm({"relevant": True, "follow": True, "comment": False, "like": True,
              "score": 1.7, "reason": "  adjacent niche  "})
    assert v["relevant"] is True
    assert v["follow"] is True and v["comment"] is False and v["like"] is True
    assert v["score"] == 1.0                      # clamped to [0,1]
    assert v["reason"] == "adjacent niche"        # trimmed


def test_string_booleans_are_parsed():
    v = norm({"follow": "yes", "comment": "false", "like": "1", "score": "0.4"})
    assert v["follow"] is True and v["comment"] is False and v["like"] is True
    assert v["score"] == 0.4


def test_relevant_defaults_to_or_of_actions():
    # No explicit 'relevant' → True if any action is recommended.
    assert norm({"follow": False, "comment": False, "like": True})["relevant"] is True
    assert norm({"follow": False, "comment": False, "like": False})["relevant"] is False


def test_bad_score_and_reason_become_none():
    v = norm({"follow": True, "score": "abc", "reason": 42})
    assert v["score"] is None
    assert v["reason"] is None
