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

The fixtures are anonymized minimal extracts shaped on the real IG 410 profile dumps of the Lab
corpus (ids, nesting and labels as captured; names and texts invented).
"""

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


class _Quiet:
    def debug(self, *a, **k):
        return None

    error = warning = info = debug


class _Dump:
    """Just what `DeviceFacade.batch_xpath_check` reads: the dump and a logger."""

    def __init__(self, xml):
        self._xml = xml
        self.logger = _Quiet()

    def get_xml_dump(self):
        return self._xml

    def batch_xpath_check(self, selectors):
        # The production evaluation, unbound: one dump, lxml, first match wins.
        return DeviceFacade.batch_xpath_check(self, selectors)


class _Profile(ProfileExtractionMixin):
    def __init__(self, xml):
        self.device = _Dump(xml)
        self.logger = _Quiet()
        self.detection_selectors = DETECTION_SELECTORS


def _flags(xml):
    return _Profile(xml).get_profile_flags_batch()


def _screen(*, title="some.account", title_desc="some.account", title_extra="",
            full_name="Some Name", category=None, bio="", actions=(), carousel=""):
    category_node = (
        f'<node resource-id="{P}profile_header_business_category" class="android.widget.TextView"'
        f' text="{category}" content-desc="" />' if category else ""
    )
    buttons = "".join(
        f'<node resource-id="{P}button_container" class="android.widget.Button" text=""'
        f' content-desc="{label}"><node resource-id="" class="android.widget.TextView"'
        f' text="{label}" content-desc="" /></node>'
        for label in actions
    )
    return f"""<hierarchy>
<node resource-id="{P}action_bar_username_container" class="android.widget.LinearLayout" text="" content-desc="">
  <node resource-id="{P}action_bar_title" class="android.widget.TextView" text="{title}" content-desc="{title_desc}" />
  {title_extra}
</node>
<node resource-id="{P}profile_header_container" class="android.widget.LinearLayout" text="" content-desc="">
  <node resource-id="{P}profile_header_full_name_above_vanity" class="android.widget.TextView" text="{full_name}" content-desc="" />
  {category_node}
  <node resource-id="{P}profile_header_bio_text" class="android.widget.TextView" text="{bio}" content-desc="" />
  <node resource-id="{P}profile_header_actions_top_row" class="android.widget.LinearLayout" text="" content-desc="">
    {buttons}
    <node resource-id="{P}row_profile_header_button_chaining" class="android.widget.Button" text="" content-desc="Contacts à découvrir" />
  </node>
  {carousel}
</node>
</hierarchy>"""


def _suggestion_card(name, desc="", badge=False):
    badge_node = (f'<node resource-id="{P}verified_badge" class="android.widget.ImageView"'
                  f' text="" content-desc="" />' if badge else "")
    return f"""<node resource-id="{P}similar_accounts_container" class="android.widget.LinearLayout" text="" content-desc="">
  <node resource-id="{P}suggested_entity_card_container" class="android.view.ViewGroup" text="" content-desc="">
    <node resource-id="{P}suggested_entity_card_name" class="android.widget.TextView" text="{name}" content-desc="{desc}" />
    {badge_node}
  </node>
</node>"""


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
    assert _flags(_screen(category="Graphiste", actions=("Suivre", "Envoyer un message")))["is_business"]


def test_a_contact_button_without_category_is_a_professional_account(lang):
    label = {"fr": "Contacts", "en": "Contact"}[lang]
    assert _flags(_screen(actions=("Follow", "Message", label)))["is_business"]


def test_our_own_professional_dashboard_is_a_professional_account(lang):
    label = {"fr": "Tableau de bord professionnel", "en": "Professional dashboard"}[lang]
    xml = _screen(actions=()).replace(
        "</hierarchy>",
        f'<node resource-id="" class="android.widget.Button" text="{label}" content-desc="" /></hierarchy>')
    assert _flags(xml)["is_business"]


def test_the_word_professional_in_a_name_or_a_bio_proves_nothing(fr):
    xml = _screen(full_name="Massage Relaxation Professionnel",
                  bio="Professionnel du bien-être depuis 10 ans",
                  actions=("Suivre", "Envoyer un message"))
    assert not _flags(xml)["is_business"]


def test_discover_people_is_not_a_contact_button(fr):
    """Our own profile's « Contacts à découvrir » chaining button carries the word, not the button."""
    assert not _flags(_screen(actions=("Modifier le profil", "Partager le profil")))["is_business"]


def test_a_contact_label_outside_the_header_row_proves_nothing(fr):
    xml = _screen(actions=("Suivre",), bio="Contacts")
    assert not _flags(xml)["is_business"]


# ------------------------------------------------------------------------------ certified signal

def test_the_badge_is_read_on_the_title_of_the_profile(lang):
    word = {"fr": "Vérifié", "en": "Verified"}[lang]
    assert _flags(_screen(title_desc=f"some.account {word}"))["is_verified"]


def test_a_badge_view_next_to_the_title_is_a_certified_account(fr):
    badge = f'<node resource-id="{P}action_bar_title_verified_badge" class="android.widget.ImageView" text="" content-desc="" />'
    assert _flags(_screen(title_extra=badge))["is_verified"]


def test_a_certified_suggestion_does_not_certify_the_profile(lang):
    word = {"fr": "Vérifié", "en": "Verified"}[lang]
    carousel = _suggestion_card("famous.brand", desc=f"famous.brand {word}", badge=True)
    assert not _flags(_screen(carousel=carousel))["is_verified"]


def test_a_plain_profile_is_neither(lang):
    flags = _flags(_screen(actions=("Follow", "Message")))
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
