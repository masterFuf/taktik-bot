"""Opening a profile means opening THAT profile.

`navigate_to_user_profile` used to return True as soon as the tap landed. On the search Users
tab that is not the same statement, and it fails in two silent ways measured on a real phone:

  - the tab also lists fan accounts carrying the searched handle as their DISPLAY name, so a tap
    can land on a stranger;
  - a search can open something that is not a profile at all (a safety interstitial, measured
    stable for 16 seconds on 43.1.4).

Both would have been interacted with and recorded under the name we were asked for.
"""

from taktik.core.social_media.tiktok.actions.atomic.navigation.search_actions import SearchActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class _SilentLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Element:
    def __init__(self, text=None, exists=False):
        self._text = text
        self.exists = exists

    def get_text(self):
        return self._text


class _Screen:
    """A screen that answers the two questions separately.

    `is_profile` drives the profile-page indicator, `handle` drives the username readers — so a
    profile whose header has not drawn yet is expressible, and is not the same thing as a screen
    that is not a profile.
    """

    def __init__(self, *, is_profile: bool, handle):
        self._is_profile = is_profile
        self._handle = handle
        self._indicators = set(PROFILE_SELECTORS.profile_page_indicator)
        self._usernames = set(PROFILE_SELECTORS.username)

    def xpath(self, selector):
        # One node answers both: the indicator list and the username list SHARE selectors (the
        # handle is both "this is a profile" and "this is whose profile"), so splitting them
        # into two kinds of fake element made a shared selector answer the indicator question
        # and swallow the handle.
        if selector in self._indicators or selector in self._usernames:
            return _Element(text=self._handle, exists=self._is_profile)
        return _Element()


def _actions(*, is_profile=True, handle=None) -> SearchActions:
    actions = SearchActions.__new__(SearchActions)
    actions.logger = _SilentLogger()
    actions.device = _Screen(is_profile=is_profile, handle=handle)
    return actions


def _check(actions, username):
    # Short settle: the fake screen never changes, so waiting the production five seconds would
    # only make the suite slower.
    return actions._landed_on_profile_of(username, settle_timeout=0.1)


def test_the_right_profile_is_accepted():
    assert _check(_actions(handle="marie"), "marie") is True


def test_the_at_sign_and_the_case_are_spelling_not_identity():
    assert _check(_actions(handle="@Marie"), "marie") is True
    assert _check(_actions(handle="marie"), "@MARIE") is True


def test_a_different_profile_is_refused():
    """The failure this exists for: a fan account whose display name carries the handle, ranked
    first on the Users tab."""
    actions = _actions(handle="mariefanpage")
    assert _check(actions, "marie") is False
    assert any("wrong profile" in message for message in actions.logger.errors)


def test_a_screen_that_is_not_a_profile_is_refused():
    """Measured on 43.1.4: a search landed on a safety interstitial and stayed there. Without
    this step the run would have "interacted" with it."""
    actions = _actions(is_profile=False, handle=None)
    assert _check(actions, "marie") is False
    assert any("not a profile" in message for message in actions.logger.errors)


def test_an_unreadable_handle_on_a_profile_is_not_a_mismatch():
    """TikTok sometimes renders the header a beat after the grid. Refusing there would turn a
    slow screen into a lost target — and this is the ONLY case where we go ahead unsure, which
    is why it is gated on being on a profile in the first place."""
    actions = _actions(is_profile=True, handle=None)
    assert _check(actions, "marie") is True
    assert actions.logger.errors == []


def test_the_indicator_is_not_only_obfuscated_ids():
    """The guard nearly shipped broken: `profile_page_indicator` held 43.1.4 ids only, and read
    0 while standing on a real profile of 46.6.3 — it would have refused every profile there.
    The handle itself is the anchor that survives both."""
    assert '//android.widget.Button[starts-with(@text, "@")]' in PROFILE_SELECTORS.profile_page_indicator
