"""fetch_own_profile must try to get back to Home on every exit path.

Device case (hashtag workflow): navigate_to_own_profile() failed verification after the
tap had already left the app off the bottom nav. The original code only called
navigate_to_home() on the success path (and only when profile info was found), so on this
exact failure the app was left stranded with no bottom nav visible, and every later
navigate_to_home/open_search call in the workflow kept failing.
"""

from taktik.core.social_media.tiktok.services.profile.profile_actions import (
    ProfileActions,
    TikTokProfileInfo,
)


def _profile(navigate_ok: bool, profile_info=None):
    profile = object.__new__(ProfileActions)
    profile.home_calls = 0

    profile.navigate_to_own_profile = lambda: navigate_ok
    profile.get_own_profile_info = lambda: profile_info
    profile._random_sleep = lambda *a, **k: None

    def _navigate_to_home():
        profile.home_calls += 1
        return True

    profile.navigate_to_home = _navigate_to_home
    return profile


def test_navigation_failure_still_recovers_to_home():
    profile = _profile(navigate_ok=False)
    assert profile.fetch_own_profile() is None
    assert profile.home_calls == 1


def test_success_with_info_returns_home():
    info = TikTokProfileInfo(username="kevin")
    profile = _profile(navigate_ok=True, profile_info=info)
    assert profile.fetch_own_profile() is info
    assert profile.home_calls == 1


def test_success_but_info_fetch_fails_still_returns_home():
    # navigate_to_own_profile succeeded but get_own_profile_info() came back empty —
    # must still attempt to return home instead of leaving the app on the profile page.
    profile = _profile(navigate_ok=True, profile_info=None)
    assert profile.fetch_own_profile() is None
    assert profile.home_calls == 1
