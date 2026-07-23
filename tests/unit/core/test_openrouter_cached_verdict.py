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
    assert e["relevant"] is True and e["follow"] is True and e["comment"] is False
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
    assert "strict relevance ladder" in with_account
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
