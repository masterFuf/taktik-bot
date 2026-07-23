"""Fail-closed normalization for account-relative engagement verdicts."""

from taktik.core.app.ai.providers.openrouter import AIService


norm = AIService._normalize_engagement


def test_none_when_missing_or_garbage():
    assert norm(None) is None
    assert norm("nope") is None
    assert norm(123) is None


def test_full_direct_verdict_is_coerced_and_clamped():
    verdict = norm({
        "relevant": True,
        "relevance_tier": "direct",
        "evidence": "  Explicit filmmaker profession  ",
        "follow": True,
        "comment": False,
        "like": True,
        "score": 1.7,
        "reason": "  direct niche  ",
    })

    assert verdict["relevant"] is True
    assert verdict["follow"] is True
    assert verdict["comment"] is True
    assert verdict["like"] is True
    assert verdict["score"] == 1.0
    assert verdict["reason"] == "direct niche"
    assert verdict["evidence"] == "Explicit filmmaker profession"


def test_action_candidates_are_derived_from_tier_not_model_booleans():
    verdict = norm({
        "relevant": "yes",
        "relevance_tier": "direct",
        "evidence": "Actor in film productions",
        "follow": "yes",
        "comment": "false",
        "like": "1",
        "score": "0.4",
    })

    assert verdict["follow"] is True
    assert verdict["comment"] is True
    assert verdict["like"] is True
    assert verdict["score"] == 0.4


def test_missing_tier_fails_closed_even_if_model_requests_actions():
    verdict = norm({
        "relevant": True,
        "follow": True,
        "comment": True,
        "like": True,
        "score": 0.95,
    })

    assert verdict["relevance_tier"] == "none"
    assert verdict["relevant"] is False
    assert verdict["follow"] is False
    assert verdict["comment"] is False
    assert verdict["like"] is False
    assert verdict["score"] == 0.2


def test_adjacent_profile_is_limited_to_discovery_like():
    verdict = norm({
        "relevant": True,
        "relevance_tier": "adjacent",
        "evidence": "Professional photographer serving film productions",
        "follow": True,
        "comment": True,
        "like": True,
        "score": 0.95,
    })

    assert verdict["relevant"] is True
    assert verdict["follow"] is False
    assert verdict["comment"] is False
    assert verdict["like"] is True
    assert verdict["score"] == 0.79


def test_weak_multihop_profile_is_never_actionable():
    verdict = norm({
        "relevant": True,
        "relevance_tier": "weak",
        "evidence": "Hair and style could be related to cultural events",
        "follow": True,
        "comment": True,
        "like": True,
        "score": 0.9,
    })

    assert verdict["relevant"] is False
    assert verdict["follow"] is False
    assert verdict["comment"] is False
    assert verdict["like"] is False
    assert verdict["score"] == 0.44


def test_positive_tier_without_evidence_is_downgraded():
    verdict = norm({
        "relevant": True,
        "relevance_tier": "direct",
        "evidence": None,
        "follow": True,
        "like": True,
        "score": 0.9,
    })

    assert verdict["relevance_tier"] == "weak"
    assert verdict["relevant"] is False


def test_bad_score_and_reason_become_none():
    verdict = norm({
        "relevant": True,
        "relevance_tier": "direct",
        "evidence": "Direct film profession",
        "follow": True,
        "score": "abc",
        "reason": 42,
    })

    assert verdict["score"] is None
    assert verdict["reason"] is None
