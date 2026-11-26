"""A profile's posts grid, shown before anything reads it.

The row under a profile's header holds up to four sub-tabs: the posts grid, Reels, Reposts and
Tagged (`PROFILE_SELECTORS.profile_sub_tabs`, the grid always first). Instagram keeps the sub-tab
our own profile was last left on until the app restarts, and a visited profile keeps the one tapped
on it while it stays open (back from one of its posts). Only the posts grid holds post thumbnails:
in every Instagram 410 dump of the corpus, the `image_button` cells are there when the grid is the
sub-tab shown and never otherwise (Reels and Reposts show a clips grid, Tagged cells without ids).

A reader that looked for thumbnails on another sub-tab found none: it scrolled the page twice
looking for them, opened no post, or counted the header's avatars as posts. Every reader of a
profile's grid calls `show_profile_posts_grid` before it reads: the one place that makes the grid
the sub-tab on screen.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from loguru import logger

from taktik.core.shared.behavior.grid_entry import GRID_COLUMNS
from taktik.core.shared.device.facade import as_device_facade
from taktik.core.shared.device.snapshot import ScreenSnapshot, SnapshotUnavailable

from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS

# After the tap: the grid tab turns selected at once, its content (thumbnails, or the empty state
# of a profile without a post) follows. A grid still loading after this is left to the reader.
GRID_SETTLE_S = 4.0

# Instagram loads a profile's grid a page at a time: a few posts on arrival, the next ones when the
# list reaches the row "loading more" under the last one. The rows after it are waited for this long.
GRID_LOAD_MORE_S = 6.0

# A grid cell says where it is in its description ("... à la ligne R, colonne C" / "row R, column C").
_GRID_POSITION_RE = re.compile(r'(?:ligne|row)\D*(\d+)\D+(?:colonne|column)\D*(\d+)', re.IGNORECASE)


@dataclass(frozen=True)
class ProfilePostsGrid:
    """What `show_profile_posts_grid` found on screen and did."""

    #: The sub-tab row is on screen. False: not a profile, a private one, or one still loading.
    has_sub_tabs: bool = False
    #: The label of the sub-tab found on screen ("Reels", "Vue Grille"...), "" without a row.
    found_on: str = ""
    #: The grid tab was tapped.
    tapped: bool = False
    #: The posts grid is the sub-tab on screen now.
    shown: bool = False
    #: The screen as it is now: the photo read when nothing was tapped, the last one after a tap.
    photo: Optional[ScreenSnapshot] = None


def show_profile_posts_grid(device, settle_s: float = GRID_SETTLE_S) -> ProfilePostsGrid:
    """Make the posts grid the sub-tab on screen when a profile shows another one.

    `device`: the Instagram device facade, or the device behind it (wrapped in it). One photo of
    the screen; when another sub-tab is shown, one humanised tap on the grid tab's own bounds, then
    the wait for the grid: its tab selected and its content shown, at most `settle_s`. Nothing is
    tapped when the row is not on screen.
    """
    facade = as_device_facade(device, DeviceFacade)
    photo = _photo_of(facade, "Profile sub-tabs not read")
    if photo is None:
        return ProfilePostsGrid()

    sub_tabs = photo.find(PROFILE_SELECTORS.profile_sub_tabs)
    if not sub_tabs:
        return ProfilePostsGrid(photo=photo)
    grid_tab = sub_tabs[0]
    found_on = next((tab.content_desc for tab in sub_tabs if tab.selected), "")
    if grid_tab.selected:
        return ProfilePostsGrid(has_sub_tabs=True, found_on=found_on, shown=True, photo=photo)

    logger.info(f"Profile shown on its '{found_on}' sub-tab: selecting the posts grid")
    if not grid_tab.bounds or not facade.human_tap(grid_tab.bounds):
        logger.warning(f"The posts grid tab could not be tapped (bounds {grid_tab.bounds}): "
                       f"the profile stays on '{found_on}'")
        return ProfilePostsGrid(has_sub_tabs=True, found_on=found_on, photo=photo)

    facade.invalidate_snapshot()
    ready = facade.wait_for_snapshot(_grid_ready, settle_s)
    if ready is not None:
        return ProfilePostsGrid(has_sub_tabs=True, found_on=found_on, tapped=True, shown=True,
                                photo=ready)

    # Not ready in time: the tab may have switched while its content is late.
    after = _photo_of(facade, "Posts grid tab tapped, not read after the tap")
    if after is None:
        return ProfilePostsGrid(has_sub_tabs=True, found_on=found_on, tapped=True)
    shown = _grid_tab_selected(after)
    if shown:
        logger.debug(f"Posts grid selected, its content not shown after {settle_s:.0f} s")
    else:
        logger.warning(f"The posts grid tab was tapped but the profile still shows '{found_on}'")
    return ProfilePostsGrid(has_sub_tabs=True, found_on=found_on, tapped=True, shown=shown,
                            photo=after)


def grid_position_of(content_desc: Optional[str]) -> Optional[int]:
    """The position of a grid cell among the profile's posts (1 = the first), from its description;
    None when the description names no row and column."""
    match = _GRID_POSITION_RE.search(content_desc or "")
    if match is None:
        return None
    return (int(match.group(1)) - 1) * GRID_COLUMNS + int(match.group(2))


@dataclass(frozen=True)
class PostsGridView:
    """What one photo shows of a profile's posts grid."""

    #: The positions of the thumbnails on screen, in the order of the screen.
    positions: Tuple[int, ...] = ()
    #: The row "loading more" is on screen: the posts after the last thumbnail are not there yet.
    loading_more: bool = False

    @property
    def first(self) -> Optional[int]:
        return min(self.positions) if self.positions else None


def posts_grid_view(photo: ScreenSnapshot) -> PostsGridView:
    """The thumbnails a photo shows, by their position, and whether the grid is loading more."""
    cells = photo.find(DETECTION_SELECTORS.post_thumbnail_selectors[0])
    positions = tuple(position for position in (grid_position_of(cell.content_desc) for cell in cells)
                      if position is not None)
    return PostsGridView(positions=positions, loading_more=photo.exists(DETECTION_SELECTORS.load_more_row))


def read_posts_grid(device) -> Optional[PostsGridView]:
    """The posts grid as the screen shows it now (one photo); None when the screen cannot be read."""
    photo = _photo_of(as_device_facade(device, DeviceFacade), "Posts grid not read")
    return posts_grid_view(photo) if photo is not None else None


def wait_for_more_posts(device, timeout_s: float = GRID_LOAD_MORE_S) -> Optional[PostsGridView]:
    """Wait for the grid to finish loading its next posts: the row "loading more" gone from the
    screen. The grid as it is then; None when it is still loading after `timeout_s`."""
    facade = as_device_facade(device, DeviceFacade)
    facade.invalidate_snapshot()
    loaded = facade.wait_for_snapshot(lambda photo: not posts_grid_view(photo).loading_more, timeout_s)
    return posts_grid_view(loaded) if loaded is not None else None


def _photo_of(facade, what: str) -> Optional[ScreenSnapshot]:
    try:
        return facade.snapshot()
    except SnapshotUnavailable as exc:
        logger.warning(f"{what}: the screen could not be dumped ({exc})")
        return None


def _grid_ready(photo: ScreenSnapshot) -> bool:
    return _grid_tab_selected(photo) and _grid_content_shown(photo)


def _grid_tab_selected(photo: ScreenSnapshot) -> bool:
    sub_tabs = photo.find(PROFILE_SELECTORS.profile_sub_tabs)
    return bool(sub_tabs) and sub_tabs[0].selected


def _grid_content_shown(photo: ScreenSnapshot) -> bool:
    return photo.exists([DETECTION_SELECTORS.post_thumbnail_selectors[0],
                         PROFILE_SELECTORS.posts_grid_empty_state])


__all__ = [
    "GRID_LOAD_MORE_S",
    "GRID_SETTLE_S",
    "PostsGridView",
    "ProfilePostsGrid",
    "grid_position_of",
    "posts_grid_view",
    "read_posts_grid",
    "show_profile_posts_grid",
    "wait_for_more_posts",
]
