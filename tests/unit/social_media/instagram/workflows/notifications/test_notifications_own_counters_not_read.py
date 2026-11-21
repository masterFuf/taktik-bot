"""The notifications scan says the counters of our own profile it could not read as unknown.

The scan reads our own profile first (`_refresh_own_account`) and announces it to the live panel as
the automation does (`active_account`). A counter not read went out as 0 (`int(... or 0)`), a value
posing as a measure. It travels as null now, on the line the automation declares.
"""

from taktik.core.contract.instagram_automation import INSTAGRAM_AUTOMATION
from taktik.core.social_media.instagram.workflows.notifications import commands


class _Runtime:
    device = object()


def test_our_counters_not_read_reach_the_app_as_unknown(monkeypatch):
    import taktik.core.social_media.instagram.actions.atomic.navigation as nav_mod
    import taktik.core.social_media.instagram.services.profile as profile_mod

    class _Profile:
        def __init__(self, device):
            pass

        def get_complete_profile_info(self, username=None, navigate_if_needed=True):
            return {"username": "own_account", "followers_count": None, "following_count": 57,
                    "posts_count": None}

    class _Nav:
        def __init__(self, device):
            pass

        def navigate_to_home(self):
            return True

    monkeypatch.setattr(profile_mod, "ProfileBusiness", _Profile)
    monkeypatch.setattr(nav_mod, "NavigationActions", _Nav)
    emitted = []
    host = commands.NotificationsHost(connect=lambda restart: None, emit=emitted.append)

    commands._refresh_own_account(host, _Runtime(), None)

    accounts = [line for line in emitted if line["type"] == "active_account"]
    assert accounts == [{"type": "active_account", "username": "own_account",
                         "followers": None, "following": 57, "posts": None}]
    declared = {field.key: field for field in INSTAGRAM_AUTOMATION.event("active_account").fields}
    assert all(declared[key].nullable for key in ("followers", "following", "posts"))
