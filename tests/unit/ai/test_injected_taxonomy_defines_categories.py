"""The injected taxonomy defines the buckets — the frozen list is only the standalone fallback.

Regression guard for the defect measured on 2026-09-02: the desktop app added a `visual_media`
niche on 2026-08-21 and asked the model to classify into it, while this module kept a hardcoded
copy of the category list that did not have it. Every profile the model correctly placed there
failed the exact-match test and was clamped to `other` — 1 115 of the 9 136 qualifications written
since, all carrying a photography or cinema sub-niche.

The rule these tests hold: a bucket the app declares is accepted the day it is declared, and a bot
running without an injected taxonomy keeps answering exactly as it did before the split.
"""
import pytest

from taktik.core.app.ai.providers.openrouter import AIService


APP_CATEGORIES = [
    'lifestyle', 'beauty_wellness', 'fitness_sports', 'fashion', 'food_drink',
    'art_design', 'visual_media', 'music_entertainment', 'business_marketing',
    'travel', 'events_services', 'tech_education', 'finance', 'health_family',
    'home_interior', 'community_causes', 'other',
]


def test_injected_bucket_is_accepted_verbatim():
    """The whole point: a key the app injected is returned as-is, not clamped to `other`."""
    assert AIService._canonicalize_niche_category('visual_media', APP_CATEGORIES) == 'visual_media'


def test_injected_bucket_is_rejected_without_the_injection():
    """And the standalone bot, which has no such niche, must not invent it."""
    assert AIService._canonicalize_niche_category('visual_media') != 'visual_media'


@pytest.mark.parametrize('raw', ['cinema', 'film_and_cinema', 'photography', 'acting', 'videography'])
def test_image_trade_synonyms_follow_the_injected_taxonomy(raw):
    """Free text naming an image trade lands in the niche that owns those trades."""
    assert AIService._canonicalize_niche_category(raw, APP_CATEGORIES) == 'visual_media'


@pytest.mark.parametrize('raw,expected', [
    # Where each one landed BEFORE the split, and must still land without an injection.
    ('cinema', 'music_entertainment'),
    ('film_and_cinema', 'music_entertainment'),
    ('acting', 'music_entertainment'),
    ('photography', 'art_design'),
    ('videography', 'art_design'),
    ('video', 'art_design'),
])
def test_standalone_falls_back_to_the_pre_split_bucket(raw, expected):
    """The fallback is keyed on the incoming slug, not on its target.

    The image trades used to be spread over two niches — camera crafts under Art & Design, screen
    crafts under Music & Entertainment. A fallback keyed on `visual_media` would collapse both onto
    one of them and silently move `cinema` out of Music & Entertainment.
    """
    assert AIService._canonicalize_niche_category(raw) == expected


def test_every_injected_key_survives_a_round_trip():
    """No key the app can send may be clamped away."""
    for category in APP_CATEGORIES:
        assert AIService._canonicalize_niche_category(category, APP_CATEGORIES) == category


def test_unknown_still_fails_closed():
    assert AIService._canonicalize_niche_category('totally_made_up', APP_CATEGORIES) == 'other'
    assert AIService._canonicalize_niche_category('', APP_CATEGORIES) == 'other'
    assert AIService._canonicalize_niche_category(None, APP_CATEGORIES) == 'other'


def test_categories_come_from_the_taxonomy_when_one_is_injected():
    """`_niche_categories` is the derivation itself — the property the whole fix rests on."""
    service = AIService.__new__(AIService)
    service.niche_taxonomy = {'visual_media': ['Portrait Photography'], 'travel': ['Solo & Budget Travel']}
    assert service._niche_categories == ['visual_media', 'travel', 'other']

    service.niche_taxonomy = {}
    assert service._niche_categories == AIService.NICHE_CATEGORIES
