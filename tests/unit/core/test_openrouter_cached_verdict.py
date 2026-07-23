"""engagement_verdict_for_known_profile: text-only engagement verdict for a profile whose AI
classification is already stored. Closes the relevance-gating cache hole — cached profiles
used to fail-open (qualification reused, verdict never computed, gate had nothing to act on) —
without re-paying the vision classification.
"""

from taktik.core.app.ai.providers.openrouter import AIService

CACHED = {
    "username": "karyu_nails",
    "niche_category": "beauty_wellness",
    "niche": "Hair & Nail Art",
    "profession": "Nail Artist",
    "biography": "ANGERS - nail art & gainage",
    "full_name": "Karyu Nails",
    "is_business": 0,
}


def _service(monkeypatch, model_text=None, success=True, capture=None):
    svc = object.__new__(AIService)
    svc.ipc = None
    svc.text_model = "test/model"
    svc.niche_taxonomy = {}

    def fake_text_completion(system_prompt, user_prompt, **kwargs):
        if capture is not None:
            capture["system"] = system_prompt
            capture["user"] = user_prompt
            capture["kwargs"] = kwargs
        if not success:
            return {"success": False, "error": "boom"}
        return {"success": True, "text": model_text, "model": "test/model", "cost_usd": 0.0001}

    monkeypatch.setattr(svc, "text_completion", fake_text_completion)
    return svc


def test_valid_verdict_is_parsed_and_normalized(monkeypatch):
    svc = _service(monkeypatch, '{"relevant": true, "relevance_tier": "direct", '
                                '"evidence": "Nail artist for beauty account", '
                                '"follow": true, "comment": false, '
                                '"like": true, "score": 0.85, "reason": "direct niche"}')
    out = svc.engagement_verdict_for_known_profile(
        "karyu_nails", CACHED, account_niche="beauty_wellness", response_language="fr")
    assert out["success"] is True
    e = out["engagement"]
    assert e["relevant"] is True and e["follow"] is True and e["comment"] is True
    assert e["score"] == 0.85
    assert e["reason"] == "direct niche"


def test_verdict_with_surrounding_text_still_parses(monkeypatch):
    svc = _service(monkeypatch, 'Sure!\n{"relevant": false, "relevance_tier": "none", '
                                '"evidence": null, "follow": false, "comment": false, '
                                '"like": false, "score": 0.1, "reason": "unrelated"}\nDone')
    out = svc.engagement_verdict_for_known_profile("x", CACHED)
    assert out["success"] is True
    assert out["engagement"]["relevant"] is False


def test_unparseable_verdict_fails_cleanly(monkeypatch):
    svc = _service(monkeypatch, "I think this profile is nice")
    out = svc.engagement_verdict_for_known_profile("x", CACHED)
    assert out["success"] is False


def test_completion_failure_propagates(monkeypatch):
    svc = _service(monkeypatch, success=False)
    out = svc.engagement_verdict_for_known_profile("x", CACHED)
    assert out["success"] is False


def test_prompt_carries_account_and_cached_niches(monkeypatch):
    # The verdict must be judged RELATIVE to the operated account (same relativity wording as the
    # vision path) and fed the profile's KNOWN classification — no screenshot involved.
    capture = {}
    svc = _service(monkeypatch, '{"relevant": true, "relevance_tier": "direct", '
                                '"evidence": "Same nail niche", "follow": true, '
                                '"comment": false, "like": true, "score": 0.7, '
                                '"reason": "ok"}', capture=capture)
    svc.engagement_verdict_for_known_profile(
        "karyu_nails", CACHED,
        account_niche="beauty_wellness",
        account_sub_niche="Nail Art",
        account_persona={
            "objective": "Sell nail training",
            "targetAudience": "Nail artists in France",
        },
        response_language="fr")
    assert "beauty_wellness" in capture["system"] and "Nail Art" in capture["system"]
    assert "Sell nail training" in capture["system"]
    assert "Nail artists in France" in capture["system"]
    assert "Hair & Nail Art" in capture["user"]              # cached niche fed as context
    assert "ANGERS" in capture["user"]                       # cached bio fed as context
    assert "French" in capture["system"]                     # reason language follows the app


def test_relativity_wording_shared_with_vision_path():
    # Single source of truth: the text-only verdict and the vision classification must use the
    # exact same relativity instruction, so "relevant" never drifts between the two paths.
    with_account = AIService._engagement_relativity("fitness", "Gym")
    assert "Niche: fitness / Gym" in with_account
    assert "evidence-based relevance ladder" in with_account
    generic = AIService._engagement_relativity(None, None)
    assert "No operated-account persona" in generic


def test_prompt_explicitly_rejects_cinema_hair_salon_and_football_shortcuts():
    prompt = AIService._engagement_relativity(
        "Cinéma, Communauté, Événements culturels",
        None,
        {
            "objective": "Build a cinema community",
            "targetAudience": "Cinema enthusiasts and filmmakers",
        },
    )

    assert "generic hair salon or football fan" in prompt
    assert "multi-hop connection" in prompt
    assert "could interest" in prompt


def test_prompt_treats_relevance_as_market_fit_not_exact_job_match():
    prompt = AIService._engagement_relativity(
        "Cinema, Community, Cultural events",
        None,
        {
            "objective": "Build a cinema community and promote events",
            "targetAudience": "Cinema enthusiasts, filmmakers and cultural professionals",
        },
    )

    assert "MARKET FIT" in prompt
    assert "not a job description" in prompt
    assert "core ecosystem" in prompt
    assert "shared customer/problem" in prompt
    assert "complementary market" in prompt
    assert "actor, filmmaker or cinematographer is direct" in prompt
    assert "musician, photographer or cultural journalist can be adjacent" in prompt
    assert "do not return weak/none" in prompt


def test_prompt_supports_cross_niche_fit_for_business_coaching():
    prompt = AIService._engagement_relativity(
        "Business coaching for beauty institutes",
        None,
        {
            "objective": "Help institute owners grow revenue and improve their management",
            "targetAudience": "Beauty institute owners, estheticians and service entrepreneurs",
        },
    )

    assert "institute owners and estheticians are direct" in prompt
    assert "shared clientele, entrepreneurial problem or complementary service" in prompt
    assert "generically entrepreneurial or creative" in prompt


def test_cached_verdict_receives_all_available_candidate_evidence(monkeypatch):
    capture = {}
    cached = {
        **CACHED,
        "profession_tags": ["coaching", "beauty business"],
        "tags": ["entrepreneurship", "revenue", "esthetician"],
        "summary": "An esthetician who teaches other institute owners how to grow.",
        "following_insights": "Mostly follows French beauty institutes and business educators.",
    }
    svc = _service(
        monkeypatch,
        '{"relevant": true, "relevance_tier": "adjacent", '
        '"evidence": "Shared beauty-business audience", "score": 0.72, "reason": "ok"}',
        capture=capture,
    )

    out = svc.engagement_verdict_for_known_profile(
        "karyu_nails",
        cached,
        account_niche="Business coaching for beauty institutes",
        account_persona={"targetAudience": "Beauty institute owners"},
    )

    assert out["success"] is True
    assert "Profession tags: coaching, beauty business" in capture["user"]
    assert "Content tags: entrepreneurship, revenue, esthetician" in capture["user"]
    assert "Profile summary: An esthetician" in capture["user"]
    assert "Audience/community signals:" in capture["user"]


def test_verdict_schema_does_not_anchor_the_model_to_none(monkeypatch):
    capture = {}
    svc = _service(
        monkeypatch,
        '{"relevant": false, "relevance_tier": "none", '
        '"evidence": null, "score": 0.1, "reason": "unrelated"}',
        capture=capture,
    )

    svc.engagement_verdict_for_known_profile("x", CACHED)

    assert '"relevance_tier": "none"' not in capture["system"]
    assert "<direct|adjacent|weak|none>" in capture["system"]
