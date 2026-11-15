"""Where the finger of a feed advance must not go down on a TikTok video.

No selector is written here: the controls are the production ones, named once in their own
catalogues (engagement rail, creator, media, bottom bar). This module only says which of them a
swipe's touch-down keeps clear of, and the band of the screen a swipe starts in when the screen
could not be read. The shared gesture engine moves a touch-down that lands on one of them into
the widest free gap of its row (`gesture_primitives._prepare_gesture_path`).

It is a VIEW, like `VIDEO_SELECTORS` (`detail.py`), not a selector catalogue: it holds no field of
its own, it reads the registered catalogues at each call, so a version override or a clone patch
of a control reaches the swipe with nothing registered here (`ui/selectors/domains.py`).
"""

from typing import List, Tuple

from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.engagement import (
    VIDEO_ENGAGEMENT_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.media import VIDEO_MEDIA_SELECTORS


class VideoGestureZones:
    """The controls of a feed video a touch-down keeps clear of. A plain class: nothing to patch."""

    @property
    def gesture_start_keep_out(self) -> Tuple[List[str], ...]:
        """Each control as its catalogue names it. Every alternative of a list is read, not only
        the first that answers: `author_username` starts with the avatar, and the name beside the
        caption is a control too (it opens the profile)."""
        return (
            # The rail on the right: like, comment, favourite, share, and the sound disc under them.
            VIDEO_ENGAGEMENT_SELECTORS.like_button,
            VIDEO_ENGAGEMENT_SELECTORS.comment_button,
            VIDEO_ENGAGEMENT_SELECTORS.favorite_button,
            VIDEO_ENGAGEMENT_SELECTORS.share_button,
            VIDEO_MEDIA_SELECTORS.sound_button,
            # The author: avatar and follow button at the top of the rail, the name above the caption.
            VIDEO_CREATOR_SELECTORS.creator_profile_image,
            VIDEO_CREATOR_SELECTORS.follow_button,
            VIDEO_CREATOR_SELECTORS.author_username,
            # The caption (a tap opens it, or a hashtag), and the bottom bar of the app.
            VIDEO_MEDIA_SELECTORS.video_description,
            NAVIGATION_SELECTORS.bottom_nav_container,
        )

    #: The screen could not be read: the touch-down is moved into this band of the width (ratios),
    #: clear of the rail. Measured on six video captures of 43.1.4, 46.9.3 and 47.0.3 (1080 px
    #: wide): the rail starts between x = 870 and 922 (0.81 to 0.85), and nothing but the caption
    #: and the author's name lie left of it. A ratio of the layout, not an id: the three versions
    #: give the same, and the version overrides patch xpaths only (`compat/selectors/setup.py`
    #: skips any other type). A layout that moves the rail is measured on a capture and changes
    #: here.
    GESTURE_FALLBACK_SAFE_X_BAND: Tuple[float, float] = (0.22, 0.70)


VIDEO_GESTURE_ZONES = VideoGestureZones()
