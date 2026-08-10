"""niche_category must always land on one of the 16 canonical buckets.

The classification prompt lists the allowed keys, but the model's answer was never validated:
real runs persisted free-text slugs into the INDEXED
profile_following.niche_category column — `fashion_and_beauty`, `personal_blog`, `spam`, and
four different spellings of the same arts concept — fragmenting one bucket across several
values and breaking any downstream aggregation (Smart Target, audience persona).
"""

from taktik.core.app.ai.providers.openrouter import AIService


def test_canonical_values_pass_through():
    for cat in AIService.NICHE_CATEGORIES:
        assert AIService._canonicalize_niche_category(cat) == cat


def test_real_drift_from_runs_626_627_is_remapped():
    # Exact slugs observed in the two real runs.
    assert AIService._canonicalize_niche_category("fashion_and_beauty") == "beauty_wellness"
    assert AIService._canonicalize_niche_category("beauty") == "beauty_wellness"
    assert AIService._canonicalize_niche_category("personal_blog") == "lifestyle"
    assert AIService._canonicalize_niche_category("personal_lifestyle") == "lifestyle"
    assert AIService._canonicalize_niche_category("food_and_drink") == "food_drink"
    assert AIService._canonicalize_niche_category("art_and_design") == "art_design"
    assert AIService._canonicalize_niche_category("arts_and_crafts") == "art_design"
    assert AIService._canonicalize_niche_category("books_and_literature") == "art_design"
    assert AIService._canonicalize_niche_category("business_and_entrepreneurship") == "business_marketing"
    assert AIService._canonicalize_niche_category("home_improvement") == "home_interior"


def test_the_four_arts_spellings_collapse_to_one_bucket():
    # The same concept arrived as four different slugs in a single run.
    variants = ["arts_and_entertainment", "arts_entertainment", "entertainment", "arts_and_culture"]
    mapped = {AIService._canonicalize_niche_category(v) for v in variants}
    assert mapped == {"music_entertainment"}


def test_invented_categories_fail_closed_to_other():
    assert AIService._canonicalize_niche_category("spam") == "other"
    assert AIService._canonicalize_niche_category("totally_made_up_bucket") == "other"
    assert AIService._canonicalize_niche_category("") == "other"
    assert AIService._canonicalize_niche_category(None) == "other"


def test_formatting_noise_is_normalized():
    # Casing, spaces and punctuation must not create a new bucket.
    assert AIService._canonicalize_niche_category("Beauty & Wellness") == "beauty_wellness"
    assert AIService._canonicalize_niche_category("  FOOD_DRINK  ") == "food_drink"
    assert AIService._canonicalize_niche_category("Art / Design") == "art_design"


def test_ambiguous_token_overlap_fails_closed():
    # "fashion_home" overlaps fashion AND home_interior equally -> no unique winner.
    # (This used to test "health_fitness", which the synonym table now answers explicitly:
    # `health_and_fitness` is in it, and the lookup no longer cares about the joiner, so
    # that input resolves rather than falling through to the overlap. Asserting it still
    # fails closed would be asserting that a known synonym is NOT applied.)
    assert AIService._canonicalize_niche_category("fashion_home") == "other"
    assert AIService._canonicalize_niche_category("travel_food") == "other"


def test_joiner_spelling_does_not_change_the_bucket():
    """"arts & culture" and "arts_and_culture" are one concept; the table holds one key.

    The model writes both. Slugified they differ by a single token, which used to send
    156 profiles on the real base into "other" while the very same concept, spelled with
    the word "and", resolved fine.
    """
    assert (AIService._canonicalize_niche_category("arts & culture")
            == AIService._canonicalize_niche_category("arts_and_culture")
            == "music_entertainment")
    assert AIService._canonicalize_niche_category("health_fitness") == "fitness_sports"


def test_batch_classification_clamps_what_the_model_returned(monkeypatch):
    """End-to-end on the batch path: a drifting model answer must be stored canonical."""
    svc = object.__new__(AIService)
    svc.ipc = None
    svc.text_model = "test/model"
    svc.model_analysis = "test/model"
    svc.niche_taxonomy = {}
    payload = (
        '{"alice": {"niche_category": "fashion_and_beauty", "niche": "Nail Art", "gender": "female"}, '
        '"bob": {"niche_category": "spam", "niche": "Other", "gender": "unknown"}}'
    )
    monkeypatch.setattr(
        svc, "text_completion",
        lambda *a, **k: {"success": True, "text": payload, "model": "test/model", "cost_usd": 0.0},
    )

    out = svc.classify_following_usernames_batch(["alice", "bob"])

    assert out["alice"]["niche_category"] == "beauty_wellness"  # was free-text fashion_and_beauty
    assert out["bob"]["niche_category"] == "other"              # invented bucket fails closed
    assert out["alice"]["niche"] == "Nail Art"                  # sub-niche label untouched
