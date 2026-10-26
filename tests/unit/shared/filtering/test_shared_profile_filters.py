"""L'evaluateur partage, et le fait qu'Instagram n'en ait plus d'autre.

Il a ete ecrit pour Instagram, puis remonte dans `shared/` le jour ou TikTok en a eu besoin. Le
deplacement s'etait arrete a mi-chemin : Instagram gardait sa copie, et ce fichier gardait les deux
d'diverger. Le basculement a ete fait le 2026-09-03, apres confrontation des deux evaluateurs sur
400 profils generes — zero verdict divergent.

Ce que ce fichier surveille a donc change de nature. Comparer la facade a ce qu'elle appelle serait
tautologique ; ce qui compte desormais est qu'elle **delegue** — qu'aucune seconde implementation ne
reapparaisse dans la classe. Le reste teste l'evaluateur partage lui-meme, sur les cas limites qui
decident si le profil d'un client est interagi ou ignore.
"""

import itertools

import pytest

from taktik.core.shared.filtering import apply_comprehensive_filter
from taktik.core.shared.filtering.profile_filters import exceeds_ceiling
from taktik.core.social_media.instagram.services.filtering import FilteringBusiness


PROFILES = [
    {},
    {"username": "clean", "followers_count": 5000, "following_count": 800, "posts_count": 120,
     "biography": "photographe a Lyon", "full_name": "Marie D", "visible_posts_count": 12},
    {"username": "private", "is_private": True, "followers_count": 900, "posts_count": 40},
    {"username": "huge", "followers_count": 2_000_000, "following_count": 12, "posts_count": 3000,
     "is_verified": True, "visible_posts_count": 9},
    {"username": "empty_shell", "followers_count": 1200, "following_count": 4000,
     "posts_count": 0, "biography": "", "visible_posts_count": 0},
    {"username": "spam", "followers_count": 300, "following_count": 20, "posts_count": 8,
     "biography": "DM me for promo, link in bio", "visible_posts_count": 2,
     "is_business": True, "visible_stories_count": 3},
    {"username": "none_followers", "followers_count": None, "posts_count": 10},
    {"username": "ratio_edge", "followers_count": 1000, "following_count": 100, "posts_count": 50,
     "visible_posts_count": 5},
]

CRITERIA = [
    {},
    {"min_followers": 1000},
    {"min_followers": 1000, "max_followers": 100_000},
    {"allow_private": True, "min_posts": 5},
    {"forbidden_bio_keywords": ["promo", "casino"]},
    {"required_bio_keywords": ["photographe"]},
    {"require_bio": True, "require_full_name": True},
    {"max_following_ratio": 2.0, "verified_penalty": 25, "business_penalty": 40},
    {"min_score": 95},
    {"min_score": 0},
]


@pytest.fixture(scope="module")
def instagram_filter():
    # The class touches neither device nor session on this path; a placeholder is enough to
    # construct it, and if that ever stops being true this fixture is where it will show.
    return FilteringBusiness(device=object(), session_manager=None)


@pytest.mark.parametrize(
    "profile,criteria", list(itertools.product(PROFILES, CRITERIA)),
    ids=lambda value: str(value.get("username", "criteria"))[:24],
)
def test_the_instagram_facade_returns_what_the_shared_evaluator_returns(
    instagram_filter, profile, criteria
):
    """Le contrat vu de l'appelant : la facade rend exactement le verdict partage."""
    assert apply_comprehensive_filter(profile, criteria) == instagram_filter.apply_comprehensive_filter(
        profile, criteria
    )


def test_the_instagram_class_holds_no_second_implementation():
    """Ce qui empeche la copie de revenir.

    Le test precedent est desormais satisfait par construction, puisque la facade appelle
    l'evaluateur partage. Celui-ci est le seul qui echouerait si quelqu'un recopiait les etages de
    filtrage dans la classe — ce qui est exactement ce qui s'etait produit la premiere fois.
    """
    etages = ("_apply_basic_filters", "_apply_advanced_filters", "_apply_content_filters",
              "_apply_behavior_filters", "_determine_final_category")
    presents = [nom for nom in etages if hasattr(FilteringBusiness, nom)]
    assert presents == [], (
        f"FilteringBusiness a retrouve une implementation propre : {presents}. "
        "L'evaluateur vit dans shared/filtering ; la classe delegue."
    )


def test_no_criteria_lets_a_reasonable_profile_through():
    """Filters ship disabled: an empty criteria dict must reject nobody."""
    verdict = apply_comprehensive_filter(PROFILES[1], {})
    assert verdict["suitable"] is True
    assert verdict["reasons"] == []


def test_the_stages_combine_by_minimum_not_by_sum():
    """Two penalties in different stages leave the score at the worse one, not at their sum."""
    verdict = apply_comprehensive_filter(
        {"username": "two_penalties", "followers_count": 1000, "following_count": 1,
         "posts_count": 0, "biography": "promo", "visible_posts_count": 0},
        {"forbidden_bio_keywords": ["promo"], "min_score": 0},
    )
    # advanced: -20 (low activity) and -30 (ratio) -> 50 ; content: -25 -> 75 ; behavior: -15 -> 85
    assert verdict["score"] == 50


def test_a_score_landing_exactly_on_the_threshold_passes():
    verdict = apply_comprehensive_filter(
        {"username": "borderline", "followers_count": 1000, "following_count": 100,
         "posts_count": 50, "visible_posts_count": 0},
        {"min_score": 85},
    )
    assert verdict["score"] == 85
    assert verdict["suitable"] is True


NASA = {"username": "nasa", "followers_count": 104_000_000, "following_count": 80,
        "posts_count": 4000, "is_verified": True, "visible_posts_count": 12}


@pytest.mark.parametrize("ceiling", [0, None], ids=["zero", "null"])
def test_a_follower_ceiling_of_zero_or_null_limits_nothing(ceiling):
    """"0: no limit" is what the pages, the CLI and the declaration say. A literal zero refused
    every profile with a single follower; a null broke the comparison and refused the profile as
    a filter error."""
    verdict = apply_comprehensive_filter(NASA, {"max_followers": ceiling})
    assert verdict["category"] != "high_followers"
    assert verdict["category"] != "error"
    assert not [reason for reason in verdict["reasons"] if reason.startswith("Too many followers")]


def test_a_follower_ceiling_still_refuses_the_profile_above_it():
    verdict = apply_comprehensive_filter(NASA, {"max_followers": 100_000})
    assert verdict["suitable"] is False
    assert verdict["category"] == "high_followers"
    assert verdict["reasons"] == ["Too many followers (104000000 > 100000)"]


#: Follows more accounts than the declared default ceiling (7500): what the evaluator never read.
FOLLOWS_MANY = {"username": "follows_many", "followers_count": 12_000, "following_count": 7_600,
                "posts_count": 300, "visible_posts_count": 12}


def test_a_following_ceiling_refuses_the_profile_above_it():
    """"Max following" is declared, sent by the page and kept by `FilterCriteria`; the evaluator
    did not read it, so a profile following 7600 accounts went through a ceiling of 7500."""
    verdict = apply_comprehensive_filter(FOLLOWS_MANY, {"max_following": 7_500})
    assert verdict["suitable"] is False
    assert verdict["category"] == "high_following"
    assert verdict["reasons"] == ["Too many following (7600 > 7500)"]


@pytest.mark.parametrize("criteria", [{"max_following": 0}, {"max_following": None}, {}],
                         ids=["zero", "null", "absent"])
def test_a_following_ceiling_of_zero_null_or_absent_limits_nothing(criteria):
    """The same rule as the follower ceiling: 0, null or absent is no limit."""
    verdict = apply_comprehensive_filter(FOLLOWS_MANY, criteria)
    assert verdict["category"] not in ("high_following", "error")
    assert not [reason for reason in verdict["reasons"] if reason.startswith("Too many following")]


@pytest.mark.parametrize("count, ceiling, over", [
    (7_600, 7_500, True), (7_500, 7_500, False), (7_600, 0, False), (7_600, None, False), (None, 10, False),
], ids=["above", "on_it", "zero", "null", "count_not_read"])
def test_the_ceiling_rule_is_one_function(count, ceiling, over):
    """The one writing of "0, null or absent limits nothing", that the evaluator and Threads call.
    A count not read (None) is never over a ceiling: refusing it would take "not read" for a
    measure."""
    assert exceeds_ceiling(count, ceiling) is over
