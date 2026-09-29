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

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from taktik.core.shared.device.facade import as_device_facade
from taktik.core.shared.device.snapshot import ScreenSnapshot, SnapshotUnavailable

from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS

# After the tap: the grid tab turns selected at once, its content (thumbnails, or the empty state
# of a profile without a post) follows. A grid still loading after this is left to the reader.
GRID_SETTLE_S = 4.0


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


__all__ = ["GRID_SETTLE_S", "ProfilePostsGrid", "show_profile_posts_grid"]
