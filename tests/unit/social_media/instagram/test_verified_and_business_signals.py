"""Certified and professional accounts: what the profile screen proves, and what the filter does.

Two settings of the Instagram automation, « Autoriser les comptes certifiés » and « Autoriser les
comptes pro », travelled to the bot and were read by nobody. Wiring them was only worth it if the
two flags they act on meant what they say, and neither did:

- ``is_business`` was the text « Professional » / « Professionnel » ANYWHERE on the screen. A bio,
  a name (« Massage Relaxation Professionnel » is a real full name seen in a following list)
  flagged a personal account, while a French professional account showing only its dashboard
  entry (« Tableau de bord professionnel », lower case) was missed.
- ``is_verified`` was « Verified » / « Vérifié » in ANY content-desc, or a bare ``verified_badge``.
  The profile header holds the « similar accounts » carousel, whose cards are other people.

The screens are real profiles, anonymized, read through the production facade: Instagram 410 in
French (Pixel 3: our own professional profile; Pixel 3a, June: our own personal profile with its
« Contacts à découvrir » carousel; a private profile) and in English (Pixel 3a, 2026-09-27: our own
professional profile, a verified media account with a « Contact » button, the account named
« Massage Relaxation Professionnel », a plain profile), and Instagram 447 in French (Pixel 6a,
2026-09-27: the same media account, and our own professional profile without a category line).

Two cases are still written by hand, no capture shows them: a title whose description carries the
word « Verified », and a certified card in the suggestions of a profile.
"""

from pathlib import Path

import pytest

from taktik.core.shared.filtering import apply_comprehensive_filter
from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    ProfileExtractionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)
from taktik.core.social_media.instagram.workflows.management.config import WorkflowConfigBuilder

P = "com.instagram.android:id/"
FIXTURES = Path(__file__).parent / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


#: Per language: our own professional profile with its category line; a professional profile with
#: a contact button and no category; our own professional profile, its dashboard entry.
CATEGORY = {"fr": "ig410_fr_own_profile_professional.xml", "en": "ig410_en_own_profile_professional.xml"}
CONTACT = {"fr": "ig447_fr_profile_verified_business.xml", "en": "ig410_en_profile_verified_business.xml"}
DASHBOARD = {"fr": "ig447_fr_own_profile_professional.xml", "en": "ig410_en_own_profile_professional.xml"}
VERIFIED_PROFILE = {"fr": "ig447_fr_profile_verified_business.xml", "en": "ig410_en_profile_verified_business.xml"}
PLAIN = {"fr": "ig410_fr_profile_follow_back.xml", "en": "ig410_en_profile_follow_back.xml"}
NAMED_PROFESSIONNEL = "ig410_en_profile_name_professionnel.xml"
OWN_PERSONAL_WITH_SUGGESTIONS = "ig410_fr_own_profile_with_suggestions.xml"


class _Quiet:
    def debug(self, *a, **k):
        return None

    error = warning = info = debug


class _Screen:
    """The phone, as far as the facade reads it: the screen's dump."""

    def __init__(self, xml):
        self._xml = xml

    def dump_hierarchy(self):
        return self._xml


class _Profile(ProfileExtractionMixin):
    def __init__(self, xml):
        # The production evaluation: the Instagram facade, one photo, first match wins.
        self.device = DeviceFacade(_Screen(xml))
        self.logger = _Quiet()
        self.detection_selectors = DETECTION_SELECTORS


def _flags(xml):
    return _Profile(xml).get_profile_flags_batch()


def _invented_header(title_desc="some.account", carousel=""):
    """Written by hand (see the module docstring): the title and the suggestions carousel only."""
    return (
        f'<hierarchy><node resource-id="{P}action_bar_title" class="android.widget.TextView" '
        f'text="some.account" content-desc="{title_desc}" />'
        f'<node resource-id="{P}profile_header_container" class="android.widget.LinearLayout" text="" '
        f'content-desc="">{carousel}</node></hierarchy>'
    )


@pytest.fixture(params=["fr", "en"])
def lang(request):
    before = active_locale()
    set_active_locale(request.param)
    yield request.param
    set_active_locale(before)


@pytest.fixture
def fr():
    before = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(before)


# --------------------------------------------------------------------------- professional signal

def test_the_category_line_under_the_name_is_a_professional_account(lang):
    xml = _capture(CATEGORY[lang])
    assert "profile_header_business_category" in xml
    assert _flags(xml)["is_business"]


def test_a_contact_button_without_category_is_a_professional_account(lang):
    xml = _capture(CONTACT[lang])
    assert "profile_header_business_category" not in xml
    assert {"fr": 'content-desc="Contacts"', "en": 'content-desc="Contact"'}[lang] in xml
    assert _flags(xml)["is_business"]


def test_our_own_professional_dashboard_is_a_professional_account(lang):
    """447 in French shows the dashboard entry without a category line; our English own profile
    shows both."""
    xml = _capture(DASHBOARD[lang])
    assert {"fr": "Tableau de bord professionnel", "en": "Professional dashboard"}[lang] in xml
    assert _flags(xml)["is_business"]


def test_the_word_professional_in_a_name_proves_nothing(lang):
    xml = _capture(NAMED_PROFESSIONNEL)
    assert "Professionnel" in xml
    assert not _flags(xml)["is_business"]


def test_discover_people_is_not_a_contact_button(fr):
    """Our own personal profile: its « Contacts à découvrir » chaining button, and the carousel
    title of the same words, carry the word, not the button."""
    xml = _capture(OWN_PERSONAL_WITH_SUGGESTIONS)
    assert xml.count("Contacts à découvrir") == 2
    assert not _flags(xml)["is_business"]


# ------------------------------------------------------------------------------ certified signal

def test_the_badge_is_read_on_the_title_of_the_profile(lang):
    word = {"fr": "Vérifié", "en": "Verified"}[lang]
    assert _flags(_invented_header(title_desc=f"some.account {word}"))["is_verified"]


def test_a_badge_view_next_to_the_title_is_a_certified_account(lang):
    xml = _capture(VERIFIED_PROFILE[lang])
    assert "action_bar_title_verified_badge" in xml
    assert _flags(xml)["is_verified"]


def test_a_certified_suggestion_does_not_certify_the_profile(lang):
    word = {"fr": "Vérifié", "en": "Verified"}[lang]
    carousel = (
        f'<node resource-id="{P}similar_accounts_container" class="android.widget.LinearLayout" '
        f'text="" content-desc=""><node resource-id="{P}suggested_entity_card_name" '
        f'class="android.widget.TextView" text="famous.brand" content-desc="famous.brand {word}" />'
        f'<node resource-id="{P}verified_badge" class="android.widget.ImageView" text="" '
        f'content-desc="" /></node>'
    )
    assert not _flags(_invented_header(carousel=carousel))["is_verified"]


def test_a_plain_profile_is_neither(lang):
    flags = _flags(_capture(PLAIN[lang]))
    assert not flags["is_verified"] and not flags["is_business"]


# ------------------------------------------------------------------------------------ the filter

VERIFIED = {"username": "v", "is_verified": True, "followers_count": 5000, "posts_count": 50,
            "following_count": 300, "visible_posts_count": 9}
BUSINESS = {"username": "b", "is_business": True, "followers_count": 5000, "posts_count": 50,
            "following_count": 300, "visible_posts_count": 9}


def test_certified_and_professional_accounts_pass_by_default():
    assert apply_comprehensive_filter(VERIFIED, {})["suitable"]
    assert apply_comprehensive_filter(BUSINESS, {})["suitable"]


def test_refusing_certified_accounts_refuses_them_only():
    criteria = {"allow_verified": False}
    verdict = apply_comprehensive_filter(VERIFIED, criteria)
    assert not verdict["suitable"] and verdict["reasons"] == ["Verified account"]
    assert apply_comprehensive_filter(BUSINESS, criteria)["suitable"]


def test_refusing_professional_accounts_refuses_them_only():
    criteria = {"allow_business": False}
    verdict = apply_comprehensive_filter(BUSINESS, criteria)
    assert not verdict["suitable"] and verdict["reasons"] == ["Business account"]
    assert apply_comprehensive_filter(VERIFIED, criteria)["suitable"]


def test_an_unread_flag_never_refuses():
    """TikTok has no business flag: absent must mean « not refused », not « refused »."""
    profile = {k: v for k, v in BUSINESS.items() if k != "is_business"}
    assert apply_comprehensive_filter(profile, {"allow_business": False})["suitable"]


# ------------------------------------------------------------- from the app's filters to the verdict

def _criteria_after_the_trip(filters):
    built = build_instagram_automation_config({
        "workflowType": "target_followers", "target": "someone", "filters": filters,
    })
    action = built["actions"][0]
    return WorkflowConfigBuilder.build_interaction_config(action)["filter_criteria"]


def test_the_two_settings_reach_the_filter():
    criteria = _criteria_after_the_trip({"allowVerified": False, "allowBusiness": False})
    assert criteria["allow_verified"] is False and criteria["allow_business"] is False
    assert not apply_comprehensive_filter(VERIFIED, criteria)["suitable"]
    assert not apply_comprehensive_filter(BUSINESS, criteria)["suitable"]


def test_a_plan_that_says_nothing_refuses_nobody_new():
    criteria = _criteria_after_the_trip({})
    assert criteria["allow_verified"] is True and criteria["allow_business"] is True
