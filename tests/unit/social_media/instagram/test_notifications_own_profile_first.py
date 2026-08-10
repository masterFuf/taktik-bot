"""A notifications scan visits our OWN profile before reading the activity feed.

The activity screen shows no follower count and carries no account header, so the scan used
to leave both untouched: the account's counters aged until some other workflow ran, and the
owning account was whatever the front passed in — missing it silently skipped the whole
persistence + dedup half.

The order is the delicate part. The activity entry lives on the HOME screen, so the profile
visit MUST hand the app back to the feed; otherwise `ensure_notifications_screen` fails its
first attempt and recovers by RESTARTING Instagram — the scan still works, and quietly pays
a relaunch every single time.
"""

import pytest

from bridges.instagram.engagement.runtime.notifications import commands


class _Bridge:
    def __init__(self):
        self.device = object()


@pytest.fixture
def _spy(monkeypatch):
    """Record the production calls the step makes, in order."""
    calls = []

    class _Profile:
        def __init__(self, device):
            calls.append('ProfileBusiness')

        def get_complete_profile_info(self, username=None, navigate_if_needed=True):
            calls.append(f'own_profile(username={username}, navigate={navigate_if_needed})')
            return _spy.profile

    class _Nav:
        def __init__(self, device):
            pass

        def navigate_to_home(self):
            calls.append('navigate_to_home')
            return True

    import taktik.core.social_media.instagram.actions.business.management.profile as profile_mod
    import taktik.core.social_media.instagram.actions.atomic.navigation as nav_mod
    monkeypatch.setattr(profile_mod, 'ProfileBusiness', _Profile)
    monkeypatch.setattr(nav_mod, 'NavigationActions', _Nav)
    monkeypatch.setattr(commands, 'emit_notif_step', lambda **kw: None)
    return calls


_spy.profile = {'username': 'own.account', 'followers_count': 648}


def test_the_own_profile_is_read_then_the_feed_is_handed_back(_spy):
    """`username=None` is what makes it the OWN profile tab rather than a search."""
    commands._refresh_own_account(_Bridge(), None)
    assert _spy == [
        'ProfileBusiness',
        'own_profile(username=None, navigate=True)',
        'navigate_to_home',
    ]


def test_the_account_read_on_screen_is_used_when_the_front_sent_none(_spy):
    assert commands._refresh_own_account(_Bridge(), None) == 'own.account'


def test_the_front_keeps_deciding_when_it_knows_the_account(_spy):
    """Pure addition: a caller that already knows the account is not overruled."""
    assert commands._refresh_own_account(_Bridge(), 'cca_gzk') == 'cca_gzk'


def test_a_failed_profile_read_still_hands_the_feed_back(monkeypatch, _spy):
    """Refreshing a counter must never cost the scan it rides in on — and above all must
    not leave Instagram parked on the profile page, where the activity entry is absent."""
    import taktik.core.social_media.instagram.actions.business.management.profile as profile_mod

    class _Broken:
        def __init__(self, device):
            pass

        def get_complete_profile_info(self, **kwargs):
            raise RuntimeError("profile screen unreachable")

    monkeypatch.setattr(profile_mod, 'ProfileBusiness', _Broken)

    assert commands._refresh_own_account(_Bridge(), 'cca_gzk') == 'cca_gzk'
    assert 'navigate_to_home' in _spy


def test_an_unreadable_profile_does_not_invent_an_account(monkeypatch, _spy):
    import taktik.core.social_media.instagram.actions.business.management.profile as profile_mod

    class _Empty:
        def __init__(self, device):
            pass

        def get_complete_profile_info(self, **kwargs):
            return None

    monkeypatch.setattr(profile_mod, 'ProfileBusiness', _Empty)
    assert commands._refresh_own_account(_Bridge(), None) is None
