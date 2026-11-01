"""The model spells a category however it likes; the bucket must not depend on that.

Measured on the real base (2026-07-28): 442 profiles sat in "other" while the model had
named a perfectly real category. The largest group — 156 of them — differed from a synonym
already in the table by nothing but the joiner: the model wrote "arts & culture", which
slugifies to `arts_culture`, against a table holding `arts_and_culture`.
"""

import pytest

from taktik.core.ai.providers.openrouter import AIService


@pytest.mark.parametrize('raw,expected', [
    # The ampersand/word difference that cost 156 profiles.
    ('arts & culture', 'music_entertainment'),
    ('arts_culture', 'music_entertainment'),
    ('Arts & Culture', 'music_entertainment'),
    ('arts_and_culture', 'music_entertainment'),
    ('Arts & Crafts', 'art_design'),
    ('arts & crafts', 'art_design'),
    # Real estate lives with the home.
    ('real_estate', 'home_interior'),
    ('realestate', 'home_interior'),
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


SPIRITUALITY_SYNONYMS = ['spiritual', 'spirituality', 'Esoteric', 'personal growth', 'personal_development']


@pytest.mark.parametrize('raw', SPIRITUALITY_SYNONYMS)
def test_spirituality_synonyms_reach_the_injected_niche(raw):
    allowed = [*AIService.NICHE_CATEGORIES, 'spirituality_growth']
    assert AIService._canonicalize_niche_category(raw, allowed) == 'spirituality_growth'


@pytest.mark.parametrize('raw', SPIRITUALITY_SYNONYMS)
def test_standalone_bot_has_no_spirituality_niche(raw):
    assert AIService._canonicalize_niche_category(raw) == 'other'


def test_free_label_examples_do_not_name_a_listed_sub_niche():
    # The prompt's two examples must stay outside any list the app injects.
    examples = AIService._FREE_LABEL_EXAMPLES
    assert 'Non-Profit' not in examples and 'Motorsport' not in examples
