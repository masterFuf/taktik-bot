"""The model spells a category however it likes; the bucket must not depend on that.

Measured on the real base (2026-07-28): 442 profiles sat in "other" while the model had
named a perfectly real category. The largest group — 156 of them — differed from a synonym
already in the table by nothing but the joiner: the model wrote "arts & culture", which
slugifies to `arts_culture`, against a table holding `arts_and_culture`.
"""

import pytest

from taktik.core.app.ai.providers.openrouter import AIService


@pytest.mark.parametrize('raw,expected', [
    # The ampersand/word difference that cost 156 profiles.
    ('arts & culture', 'music_entertainment'),
    ('arts_culture', 'music_entertainment'),
    ('Arts & Culture', 'music_entertainment'),
    ('arts_and_culture', 'music_entertainment'),
    ('Arts & Crafts', 'art_design'),
    ('arts & crafts', 'art_design'),
    # Kevin's call: an estate agent sells a service, so real estate is business.
    ('real_estate', 'business_marketing'),
    ('realestate', 'business_marketing'),
    ('shopping', 'business_marketing'),
    ('retail', 'business_marketing'),
    # Whole-token overlap can never bridge these: "technology" does not contain "tech"
    # as a token, and "books" shares nothing with "art_design".
    ('technology', 'tech_education'),
    ('books', 'art_design'),
    ('social_issues', 'community_causes'),
])
def test_variants_reach_their_bucket(raw, expected):
    assert AIService._canonicalize_niche_category(raw) == expected


@pytest.mark.parametrize('raw', ['spam', 'unknown', '', None, '???'])
def test_meaningless_input_fails_closed(raw):
    assert AIService._canonicalize_niche_category(raw) == 'other'


@pytest.mark.parametrize('raw', ['automotive', 'pets', 'nightlife', 'spirituality'])
def test_genuinely_unmapped_stays_other(raw):
    """These have no bucket and no owner decision yet — failing closed is correct.

    Guessing one would be worse than "other": a wrong bucket is invisible, an "other" is
    a question the operator can see.
    """
    assert AIService._canonicalize_niche_category(raw) == 'other'


def test_canonical_buckets_pass_through():
    for bucket in AIService.NICHE_CATEGORIES:
        assert AIService._canonicalize_niche_category(bucket) == bucket
