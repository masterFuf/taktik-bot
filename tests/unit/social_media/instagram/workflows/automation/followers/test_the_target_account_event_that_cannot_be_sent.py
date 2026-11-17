"""The opening of a Target source says an event it could not send, and goes on as before.

Once the source's profile is open, the setup sends the app the account it works (`target_account`:
followers, following, posts). A value the line cannot carry used to be swallowed (`except: pass`): the
panel showed no source and nothing said why. The run itself never depended on that line, and still
does not: the list is opened all the same.
"""

from types import SimpleNamespace

from loguru import logger

from taktik.core.social_media.instagram.workflows.automation.followers.workflows.direct.navigation_helpers import (
    DirectNavigationMixin,
)


class _PostCount:
    """A count the profile reader handed back as an object, which a JSON line cannot carry."""


def _setup():
    """The mixin with only what its setup touches: a profile that opens, a list that opens."""
    setup = object.__new__(DirectNavigationMixin)
    setup.logger = logger
    setup._human_like_delay = lambda kind: None
    setup.opened = []
    setup.nav_actions = SimpleNamespace(
        navigate_to_profile=lambda *args, **kwargs: True,
        open_followers_list=lambda: setup.opened.append('followers') or True,
        open_following_list=lambda: setup.opened.append('following') or True,
    )
    setup.profile_business = SimpleNamespace(get_complete_profile_info=lambda *args, **kwargs: {
        'is_private': False, 'followers_count': 5400, 'following_count': 300, 'media_count': _PostCount(),
    })
    return setup


def test_the_event_not_sent_is_said_and_the_list_still_opened():
    setup = _setup()
    said = []
    sink = logger.add(lambda message: said.append(message.record['message']), level='WARNING')
    try:
        followers_count, profile_info = setup._setup_direct_workflow(
            'a_target', {}, {'interaction_type': 'followers'}, 0, False)
    finally:
        logger.remove(sink)

    assert followers_count == 5400 and profile_info is not None
    assert setup.opened == ['followers'], "the list must be opened whether the line was sent or not"
    assert any('@a_target' in line and 'not JSON serializable' in line for line in said), said
