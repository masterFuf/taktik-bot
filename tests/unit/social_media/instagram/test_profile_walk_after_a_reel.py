"""After leaving a Reel, the walk through a profile's posts resumes PAST the furthest post reached.

Run case (Instagram, followers-of-a-target workflow, likes on a visited profile of some ninety posts
whose grid shows 6 thumbnails): the bot saw 16 publications to leave 4 likes, about 7 of them twice.
The journal gives the absolute grid position of every cell opened (`grid_entry_choice`):

1. opens cell 1, likes it, advances to 2: a Reel, back to the grid;
2. reopens cell 6 (never opened), advances to 7 and 8, reaches 9: a Reel, liked, back to the grid;
3. reopens cell 5 (never opened either), advances to 6, 7, 8 (all seen) and 9: the Reel again;
4. reopens cell 4 and walks 5, 6, 7, 8 once more.

No post was liked twice (a known signature is skipped), but the walk went round in circles: slow,
repetitive, not human. A reopen only avoided the CELLS already opened, while the viewer walks the
profile one position at a time: a cell never opened that sits before the furthest position reached
leads straight back through posts already seen.

The profile below is a double of the viewer and its grid (absolute positions, the Reels of the run,
invented counters). The session memory and its draws are the real ones, except for the cells the
run's dice drew, replayed whenever the code under test still offers them.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.instagram.services.like.orchestration as orchestration
import taktik.core.social_media.instagram.services.like.post_navigation as post_navigation
from taktik.core.shared.behavior.grid_entry import GRID_COLUMNS
from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.instagram.services.like.orchestration import (
    LikeOrchestration,
)

USERNAME = "profil_exemple"
POSTS_ON_PROFILE = 90
#: The two Reels the run met, at their grid positions.
REELS_OF_THE_RUN = {2, 9}
#: The cells the run's dice drew: the entry, then one reopen after each Reel.
CELLS_DRAWN_BY_THE_RUN = [1, 6, 5, 4]
#: The run liked position 1 and the Reel at 9 (whose like counter then read one more).
LIKED_BY_THE_RUN = {1, 9}


class _Log:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


class _Profile:
    """A profile's grid and its post viewer, one absolute position at a time.

    Under the header the grid shows two rows (6 thumbnails, as on the run's phone); once scrolled,
    four. A grid scroll moves it by two rows, like the 0.40-screen seek gesture on that phone. A
    like moves the post's like counter up by one, as Instagram's did.
    """

    ROWS_UNDER_THE_HEADER = 2
    ROWS_ONCE_SCROLLED = 4
    ROWS_PER_GRID_SCROLL = 2

    def __init__(self, reels, posts=POSTS_ON_PROFILE):
        self.posts = posts
        self.reels = set(reels)
        # Distinct (likes, comments) per post: the loop tells posts apart by these counters.
        self.counters = {
            position: (100 + 7 * position, position % 5) for position in range(1, posts + 1)
        }
        #: Header descriptions by position; none = a screen without a framed header.
        self.headers = {}
        self.top_row = 1
        self.current = None
        self.liked = set()
        #: Every position the viewer showed, in order.
        self.landings = []
        #: Every position opened from the grid.
        self.grid_opens = []
        #: Vertical gestures the viewer will swallow (the post stays on screen).
        self.swallowed_advances = 0

    # grid
    def visible_cells(self):
        rows = self.ROWS_UNDER_THE_HEADER if self.top_row == 1 else self.ROWS_ONCE_SCROLLED
        first = (self.top_row - 1) * GRID_COLUMNS + 1
        last = min(self.posts, first + rows * GRID_COLUMNS - 1)
        return [self._cell(position) for position in range(first, last + 1)]

    def _cell(self, position):
        row, column = (position - 1) // GRID_COLUMNS + 1, (position - 1) % GRID_COLUMNS + 1
        kind = "Reel" if position in self.reels else "Photo"
        return SimpleNamespace(
            attrib={"content-desc": f"{kind} de exemple, à la ligne {row}, colonne {column}"},
            position=position,
        )

    def scroll_grid(self):
        last_row = (self.posts - 1) // GRID_COLUMNS + 1
        if self.top_row + self.ROWS_ONCE_SCROLLED > last_row:
            return False
        self.top_row += self.ROWS_PER_GRID_SCROLL
        return True

    def open(self, position):
        self.current = position
        self.landings.append(position)
        self.grid_opens.append(position)
        return True

    # viewer
    def advance(self):
        if self.current is None or self.current >= self.posts:
            return False
        if self.swallowed_advances:
            self.swallowed_advances -= 1
            return True
        self.current += 1
        self.landings.append(self.current)
        return True

    def back(self):
        self.current = None
        return True

    def framed_header(self):
        return self.headers.get(self.current)

    def framed_signature(self):
        header = self.framed_header()
        if header is None:
            return None
        likes, comments = self.counters[self.current]
        return f"{header} | {likes} {comments}"

    def like(self):
        likes, comments = self.counters[self.current]
        self.counters[self.current] = (likes + 1, comments)
        self.liked.add(self.current)
        return True


class _ViewerGestures:
    """The production gesture owner, reduced to what moves the double."""

    def __init__(self, profile):
        self.profile = profile

    @staticmethod
    def _plan_behavior_gesture(_context, _gesture):
        return {"distance_scale": 1.0, "velocity_scale": 1.0, "settle_scale": 1.0, "dwell_scale": 1.0}

    @staticmethod
    def _choose_advance_mode(_context, base_drag_probability):
        return {"mode": "flick", "distance_scale": 1.0, "velocity_scale": 1.0, "dwell_scale": 1.0}

    def _strong_flick(self, *_args, **_kwargs):
        return self.profile.advance()

    def _long_drag(self, *_args, **_kwargs):
        return self.profile.advance()

    def _human_swipe(self, *_args, **_kwargs):
        return self.profile.advance()

    @staticmethod
    def land_on_post_header(**_kwargs):
        return {}

    def framed_post_identity(self):
        return self.profile.framed_header()

    def framed_post_signature(self):
        return self.profile.framed_signature()


class _SessionWithTheRunsDice(BehaviorSessionState):
    """The real session memory and draws, except for the cells the run's dice drew.

    Each grid choice consumes one draw of the run: the cell is taken when the code under test
    offers it (and it is unseen, as the real chooser would require); otherwise the real draw decides
    among what is offered.
    """

    def __init__(self, drawn_positions, seed):
        super().__init__(seed=seed)
        self._drawn = list(drawn_positions)

    def choose_grid_entry_index(self, *, context, candidate_keys, avoid_recent=2, require_unseen=False):
        keys = [str(key) for key in candidate_keys]
        wanted = self._drawn.pop(0) if self._drawn else None
        wanted_key = f"{context}:position:{wanted}"
        remembered = {
            item.get("key") for item in self.grid_entry_history if item.get("context") == context
        }
        if wanted_key in keys and not (require_unseen and wanted_key in remembered):
            return keys.index(wanted_key)
        return super().choose_grid_entry_index(
            context=context,
            candidate_keys=keys,
            avoid_recent=avoid_recent,
            require_unseen=require_unseen,
        )


def _walker(monkeypatch, profile, session, liked_positions):
    """The production like loop and navigation, on the double. Returns the glances list."""
    host = object.__new__(LikeOrchestration)
    host.logger = _Log()
    host.default_config = {}
    host.behavior_state = session
    host.device = SimpleNamespace(get_screen_size=lambda: (1080, 2280))
    host.detection_selectors = SimpleNamespace(post_thumbnail_selectors=("grid-thumbnail",))
    host.post_selectors = SimpleNamespace(next_post_button_selectors=())
    host.scroll_actions = _ViewerGestures(profile)

    # The grid and the viewer.
    host._visible_grid_thumbnails = lambda _selector: profile.visible_cells()
    host._session_grid_scroll = lambda *_args, **_kwargs: profile.scroll_grid()
    host._human_tap_grid_thumbnail = lambda cell: profile.open(cell.position)
    host._is_in_post_view = lambda: profile.current is not None
    host._return_to_profile_from_post = profile.back
    host._emit_entry_decision = lambda *_args, **_kwargs: None

    # What the loop reads on the open post, and the like.
    host._is_current_post_reel = lambda: profile.current in profile.reels
    host._extract_likes_count_from_ui = lambda **_kwargs: profile.counters[profile.current][0]
    host._extract_comments_count_from_ui = lambda **_kwargs: profile.counters[profile.current][1]
    host._is_post_already_liked = lambda: profile.current in profile.liked
    engaged = []

    def engage(_sequence, *_args):
        engaged.append(profile.current)
        return profile.like(), False

    host._run_engagement_sequence = engage
    host._behavior_reading_scale = lambda _context: 1.0
    host._human_like_delay = lambda *_args, **_kwargs: None
    host._action_timestamp = lambda: "at-the-gesture"

    glances = []

    def glance(_prose_len):
        glances.append(profile.current)
        return 1.0

    for module in (orchestration, post_navigation):
        monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
        # Wherever a glance is spelled, it is counted (`raising=False`: a module that no longer
        # glances itself must not break the count).
        monkeypatch.setattr(module, "content_dwell", glance, raising=False)
    monkeypatch.setattr(post_navigation, "plan_prescroll", lambda _posts_count: 0)
    monkeypatch.setattr(orchestration, "plan_engagement_sequence", lambda *_args: ("like",))
    # The like draw of each new post: the posts the run liked, and those only.
    monkeypatch.setattr(
        orchestration.random,
        "random",
        lambda: 0.0 if profile.current in liked_positions else 0.99,
    )
    return host, glances, engaged


def test_the_runs_walk_never_goes_back_through_posts_already_seen(monkeypatch):
    profile = _Profile(REELS_OF_THE_RUN)
    session = _SessionWithTheRunsDice(CELLS_DRAWN_BY_THE_RUN, seed=90)
    host, _glances, _engaged = _walker(monkeypatch, profile, session, LIKED_BY_THE_RUN)

    result = host.like_posts_with_sequential_scroll(
        USERNAME, max_likes=4, profile_data={"posts_count": POSTS_ON_PROFILE}
    )

    # The first two draws of the run are still possible: 1, then 6 after the Reel at 2.
    assert profile.landings[:6] == [1, 2, 6, 7, 8, 9]
    # The run then reopened 5 and walked 6, 7, 8 again. Every landing must be a new position,
    # further than all the previous ones.
    assert profile.landings == sorted(set(profile.landings)), (
        f"the viewer walked {profile.landings}"
    )
    assert profile.landings[6] > 9
    assert result["posts_seen"] == result["unique_posts_seen"] == 20


@pytest.mark.parametrize("seed", range(40))
def test_every_reopen_after_a_reel_lands_past_the_furthest_post_reached(monkeypatch, seed):
    # Reels spread over the first rows, two of them side by side.
    profile = _Profile({2, 5, 9, 10, 16, 23})
    session = BehaviorSessionState(seed=seed)
    host, _glances, _engaged = _walker(monkeypatch, profile, session, liked_positions=set())

    host.like_posts_with_sequential_scroll(
        USERNAME, max_likes=4, profile_data={"posts_count": POSTS_ON_PROFILE}
    )

    furthest = 0
    for landing in profile.landings:
        assert landing > furthest, f"seed {seed}: the viewer walked {profile.landings}"
        furthest = landing
    reopens = profile.grid_opens[1:]
    assert reopens, "the profile has Reels in its first rows: the walk must have left one"


def test_a_post_met_again_gets_no_glance_and_no_reading(monkeypatch):
    # The vertical gesture after the first post is swallowed: the same post is still on screen.
    profile = _Profile(reels=set())
    profile.swallowed_advances = 1
    session = BehaviorSessionState(seed=3)
    host, glances, engaged = _walker(monkeypatch, profile, session, liked_positions=set())

    host.like_posts_with_sequential_scroll(
        USERNAME, max_likes=1, profile_data={"posts_count": POSTS_ON_PROFILE}
    )

    # One glance per post, taken once the loop knows the post is new: none on the post met again.
    entry = profile.grid_opens[0]
    assert glances[:2] == [entry, entry + 1], f"glances at {glances}"
    assert glances == sorted(set(glances))
    assert engaged == []


def test_a_reopen_after_a_reel_is_not_always_the_very_next_post(monkeypatch):
    # Entry on cell 1, then the Reel at 2: the reopen draws among the cells past it on screen.
    reopened = set()
    for seed in range(60):
        profile = _Profile({2})
        session = _SessionWithTheRunsDice([1], seed=seed)
        host, _glances, _engaged = _walker(monkeypatch, profile, session, liked_positions=set())
        host.like_posts_with_sequential_scroll(
            USERNAME, max_likes=4, profile_data={"posts_count": POSTS_ON_PROFILE}
        )
        reopened.add(profile.grid_opens[1])

    assert reopened <= {3, 4, 5, 6}
    assert 3 in reopened and len(reopened) > 1


#: The counters the loop read on a small account of the run, post after post (likes, comments):
#: nine readings, four of them already met, although the walk never went back.
SMALL_ACCOUNT_COUNTERS = [(4, 0), (5, 0), (8, 1), (8, 1), (7, 0), (4, 0), (6, 0), (6, 0), (6, 0), (4, 0)]


def test_posts_of_a_small_account_sharing_their_counters_are_not_taken_as_already_seen(
    monkeypatch,
):
    profile = _Profile(reels=set())
    for position, counters in enumerate(SMALL_ACCOUNT_COUNTERS, start=1):
        profile.counters[position] = counters
        profile.headers[position] = f"auteur_exemple a publié un(e) photo il y a {position} semaines"
    session = _SessionWithTheRunsDice([1], seed=5)
    host, glances, _engaged = _walker(monkeypatch, profile, session, liked_positions=set())

    result = host.like_posts_with_sequential_scroll(
        USERNAME, max_likes=2, profile_data={"posts_count": POSTS_ON_PROFILE}
    )

    assert profile.landings == list(range(1, len(SMALL_ACCOUNT_COUNTERS) + 1))
    assert result["unique_posts_seen"] == result["posts_seen"] == len(SMALL_ACCOUNT_COUNTERS), (
        "distinct posts with equal counters were skipped as already seen"
    )
    assert glances == profile.landings
