"""The stories of the feed tray: filed under their author, and stopped by the first refusal.

The tray loop (`StoryBusiness.view_feed_stories`) never ran from the desktop until the feed
runner stopped dropping `view_feed_stories`. Read before letting it run: a slide whose author
it could not read was watched, liked and reacted to, and filed under the literal name
'unknown'; and no gesture was followed by a look for Instagram's "Try again later", nor did the
loop read the run's stop lock, where the profile story loop does both.
"""

import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.actions.story import StoryBusiness


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


def _story(titles, blocked_after=None):
    """A tray of friends; `titles[i]` is what the viewer header reads for friend i."""
    story = StoryBusiness.__new__(StoryBusiness)
    story.logger = _log()
    story.default_config = {
        'max_stories_per_profile': 1, 'max_feed_profiles': len(titles),
        'view_duration_range': (0, 0), 'navigation_delay_range': (0, 0),
        'like_probability': 1.0, 'reaction_probability': 1.0, 'reaction': 'laugh',
    }
    story.rows = []
    story.gestures = []
    story.opened = []
    story._record_action = lambda u, k, c=1, **kw: story.rows.append((u, k))
    story._human_like_delay = lambda kind: None
    story._story_view_duration = lambda config: 0
    story._wait_after_story_advance = lambda config: None
    story._plan_story_engagement = lambda config, n: ({0}, {0})
    story._press_back = lambda n=1: None

    def _blocked(username, action):
        return blocked_after is not None and len(story.gestures) >= blocked_after

    story._stop_if_action_blocked = _blocked
    story.nav_actions = types.SimpleNamespace(
        navigate_to_home=lambda: True, navigate_to_next_story=lambda settle=False: False)
    story.detection_actions = types.SimpleNamespace(
        count_visible_feed_stories=lambda skip_own_story=True: len(titles),
        is_story_viewer_open=lambda: True,
        get_story_viewer_metadata=lambda: {'title': titles[story.opened[-1]], 'is_ad': False},
    )
    story.click_actions = types.SimpleNamespace(
        click_feed_story=lambda i, skip_own_story=True: story.opened.append(i) or True,
        like_story=lambda: story.gestures.append('like') or True,
        react_to_story=lambda reaction=None, emoji_index=None: story.gestures.append('react') or True,
        close_story=lambda: None,
        scroll_feed_stories_left=lambda: False,
    )
    return story


@pytest.fixture(autouse=True)
def _clean_lock():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def test_each_tray_gesture_is_filed_under_the_friend():
    story = _story(['alice'])

    story.view_feed_stories()

    assert story.rows == [('alice', 'STORY_WATCH'), ('alice', 'STORY_LIKE'), ('alice', 'STORY_REACTION')]


def test_a_slide_whose_author_cannot_be_read_is_not_engaged_nor_filed():
    story = _story([None, 'bob'])

    stats = story.view_feed_stories()

    assert ('unknown', 'STORY_WATCH') not in story.rows
    assert all(user == 'bob' for user, _kind in story.rows)
    assert story.gestures == ['like', 'react'], "only bob's slide is liked and reacted to"
    assert stats['stories_viewed'] == 2


def test_the_first_refused_like_ends_the_tray():
    story = _story(['alice', 'bob', 'carol'], blocked_after=1)

    story.view_feed_stories()

    assert story.gestures == ['like']
    assert story.opened == [0]


def test_the_tray_reads_a_lock_set_elsewhere():
    story = _story(['alice', 'bob'])
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "le telephone ne repond plus")

    story.view_feed_stories()

    assert story.opened == [] and story.gestures == []


def test_a_refused_like_is_not_filed_and_the_viewer_stays_open():
    """The like was filed before the look, and the viewer closed after it: a refused gesture
    counted, then a swipe that closes the dialog, which is acting again."""
    story = _story(['alice', 'bob'], blocked_after=1)
    closed = []
    story.click_actions.close_story = lambda: closed.append(True)

    stats = story.view_feed_stories()

    assert ('alice', 'STORY_LIKE') not in story.rows
    assert stats['stories_liked'] == 0
    assert closed == []
    assert stats['stop_reason'] == 'action_blocked'


def test_a_refused_reaction_is_not_filed():
    story = _story(['alice'], blocked_after=2)

    stats = story.view_feed_stories()

    assert story.gestures == ['like', 'react']
    assert ('alice', 'STORY_REACTION') not in story.rows and stats['stories_reacted'] == 0
