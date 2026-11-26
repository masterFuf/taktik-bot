"""The grid pre-scroll of the entry into a profile's posts is counted on the screen.

Run case (Instagram, likes on the posts of a visited profile, eight runs on three phones): when the
entry scrolled the grid before it opened a post, it ended on one of the first two rows 63 times out
of 77 after one flick, 9 out of 21 after two. Instagram loads the grid a page at a time: a few posts
on arrival (nine, three, twelve), the next ones when the list reaches the row "loading more" under
the last one. The flick stopped there, the thumbnails were read less than a second later, and the
entry was drawn among the first rows.

The screens are real, anonymized: Instagram 410.0.0.53.71 in French on a Pixel 3a (1080x2220).

- one profile's grid as the phone showed it during the pre-scroll of two screens: on arrival
  (posts 1 to 3 under a tall header), its header folded (1 to 12), a flick further with the row
  "loading more" (10 to 21), the next posts loaded (10 to 24), a flick further and loading again
  (22 to 33), loaded (22 to 36);
- another profile's grid when a flick moved nothing: before it (46 to 57), stopped at the row
  "loading more" (46 to 57), the next posts loaded (46 to 60), a flick further (58 to 69).
"""

import pytest
from loguru import logger

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.instagram.services.like.post_navigation as post_navigation
from profile_posts_phone import PKG, ProfilePostsPhone, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.navigation.profile_grid import (
    GRID_LOAD_MORE_S,
    posts_grid_view,
    read_posts_grid,
    wait_for_more_posts,
)
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.services.like.orchestration import LikeOrchestration
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS

GRID = "ig410_fr_profile_grid_prescroll_"
ARRIVAL = GRID + "a_arrival.xml"                    # posts 1 to 3
HEADER_FOLDED = GRID + "b_header_folded.xml"        # posts 1 to 12
LOADING_MORE = GRID + "c_loading_more.xml"          # posts 10 to 21, the row "loading more"
MORE_LOADED = GRID + "d_more_loaded.xml"            # posts 10 to 24
LOADING_AGAIN = GRID + "e_loading_again.xml"        # posts 22 to 33, the row "loading more"
LOADED = GRID + "f_loaded.xml"                      # posts 22 to 36
STALL_BEFORE = GRID + "stall_a_before.xml"          # posts 46 to 57
STALL_STOPPED = GRID + "stall_b_stopped_loading.xml"   # posts 46 to 57, the row "loading more"
STALL_LOADED = GRID + "stall_c_loaded.xml"          # posts 46 to 60
STALL_MOVED_ON = GRID + "stall_d_moved_on.xml"      # posts 58 to 69


class _GridPhone(ProfilePostsPhone):
    """The grid replayed: each flick shows the next capture; a capture named in `loads` turns into
    the next one by itself after that many dumps (the posts Instagram was loading have arrived)."""

    def __init__(self, names, loads=None):
        super().__init__(screen=capture(names[0]), height=2220)
        self.captures = [capture(name) for name in names]
        self.names = list(names)
        self.loads = dict(loads or {})
        self.shown = 0
        self.dumps_of_shown = 0
        self.flicks = 0

    def _show_next(self):
        self.shown = min(self.shown + 1, len(self.captures) - 1)
        self.dumps_of_shown = 0

    def flick(self):
        self.flicks += 1
        self._show_next()

    def dump_hierarchy(self, *_a, **_k):
        wait = self.loads.get(self.names[self.shown])
        if wait is not None and self.dumps_of_shown >= wait:
            self._show_next()
        self.dumps_of_shown += 1
        return self.captures[self.shown]


class _Flicks:
    """The scroll owner's part of a grid flick (`ScrollActions` in production), moving the phone."""

    def __init__(self, phone):
        self.phone = phone

    def _plan_behavior_gesture(self, _context, _kind):
        return {"distance_scale": 1.0, "velocity_scale": 1.0, "settle_scale": 1.0}

    def _strong_flick(self, _direction, distance_px=None, velocity_scale=1.0):
        self.phone.flick()
        return True


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    """The pauses of the code under test cost no time: the posts of a capture that loads arrive
    after a number of dumps, not of seconds."""
    for module in (snapshot_module, post_navigation):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)


def _like(phone, said=None):
    like = object.__new__(LikeOrchestration)
    like.device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    like.scroll_actions = _Flicks(phone)
    like.logger = logger.bind(module="test_grid_prescroll")
    if said is not None:
        logger.add(lambda message: said.append(message.record["message"]), level="DEBUG")
    return like


def _positions(like):
    view = read_posts_grid(like.device)
    return (min(view.positions), max(view.positions)), view.loading_more


# --- what a photo of the grid says


def test_a_photo_of_the_grid_gives_its_positions_and_whether_it_is_loading_more():
    like = _like(_GridPhone([LOADING_MORE]))

    assert _positions(like) == ((10, 21), True)

    like = _like(_GridPhone([MORE_LOADED]))
    assert _positions(like) == ((10, 24), False)


def test_the_arrival_shows_the_first_posts_only():
    view = posts_grid_view(_like(_GridPhone([ARRIVAL])).device.snapshot())

    assert view.positions == (1, 2, 3) and view.first == 1 and view.loading_more is False


# --- the pre-scroll, as the phone played it


def test_two_screens_down_the_grid_are_two_screens_the_grid_really_went_down():
    phone = _GridPhone(
        [ARRIVAL, HEADER_FOLDED, LOADING_MORE, MORE_LOADED, LOADING_AGAIN, LOADED],
        loads={LOADING_MORE: 2, LOADING_AGAIN: 2},
    )
    like = _like(phone)

    gone = like._prescroll_profile_grid(2)

    # The first flick only folds the header (the grid still starts at its first post): it does not
    # count. The two that follow each move the grid on, the posts loading after the first of them
    # waited for before the second.
    assert gone == 2 and phone.flicks == 3
    # The grid the entry is drawn on has finished loading, and starts at post 22, not at post 1.
    assert _positions(like) == ((22, 36), False)


def test_a_flick_the_list_stopped_short_of_is_made_again_once_the_next_posts_are_there():
    phone = _GridPhone(
        [STALL_BEFORE, STALL_STOPPED, STALL_LOADED, STALL_MOVED_ON],
        loads={STALL_STOPPED: 2},
    )
    like = _like(phone)

    gone = like._prescroll_profile_grid(1)

    # The first flick moved nothing (posts 46 to 57 before and after, the row "loading more" under
    # them): the next posts are waited for, and the flick made again.
    assert gone == 1 and phone.flicks == 2
    assert _positions(like) == ((58, 69), False)


def test_a_grid_that_never_loads_its_next_posts_is_drawn_as_it_is_and_said(monkeypatch):
    said = []
    phone = _GridPhone([STALL_BEFORE, STALL_STOPPED])      # the row "loading more" stays
    like = _like(phone, said)
    waited = []

    def wait_until_the_timeout(device):
        waited.append(GRID_LOAD_MORE_S)
        return wait_for_more_posts(device, timeout_s=0.0)    # the wait's last look, without its seconds

    monkeypatch.setattr(post_navigation, "wait_for_more_posts", wait_until_the_timeout)

    gone = like._prescroll_profile_grid(2)

    assert gone == 0 and phone.flicks == 1, "a flick was made while the grid was still loading"
    assert waited == [GRID_LOAD_MORE_S]
    assert any("still loading its next posts" in message for message in said)


def test_a_flick_that_changes_nothing_with_nothing_loading_is_the_end_of_the_grid():
    phone = _GridPhone([LOADED, LOADED, LOADED, LOADED])
    like = _like(phone)

    gone = like._prescroll_profile_grid(3)

    assert gone == 0 and phone.flicks == 1


def test_the_entry_reports_the_screens_really_gone_down(monkeypatch):
    phone = _GridPhone(
        [ARRIVAL, HEADER_FOLDED, LOADING_MORE, MORE_LOADED, LOADING_AGAIN, LOADED],
        loads={LOADING_MORE: 2, LOADING_AGAIN: 2},
    )
    like = _like(phone)
    seen = {}
    monkeypatch.setattr(post_navigation, "plan_prescroll", lambda _posts_count: 2)
    monkeypatch.setattr(post_navigation, "show_profile_posts_grid", lambda _device: None)

    def choose(posts, username=None, candidates=None, **_kw):
        seen["positions"] = [like._grid_entry_position(post, index) for index, post in enumerate(posts)]
        return None     # no entry drawn: the test stops at what the draw was offered

    monkeypatch.setattr(like, "_choose_session_grid_entry", choose)
    monkeypatch.setattr(like, "_open_first_post_of_profile", lambda username=None: False)
    like.detection_selectors = DETECTION_SELECTORS

    like._open_entry_post_of_profile(posts_count=676)

    # The draw is offered the posts the pre-scroll reached, never the first rows again.
    assert min(seen["positions"]) == 22 and max(seen["positions"]) == 36
