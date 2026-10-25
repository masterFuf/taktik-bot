"""Liker extraction — read the usernames of the open likers popup."""

import time
from typing import TYPE_CHECKING, Any, Callable, List

if TYPE_CHECKING:
    from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors

#: How long the likers sheet may take to come up after the tap on a like counter before the reading
#: refuses (seconds), and how often it looks meanwhile.
LIKERS_SHEET_ARRIVAL_S = 3.0
LIKERS_SHEET_POLL_S = 0.5


class LikerExtractionMixin:
    """Mixin: the reading of the open likers popup (`_extract_likers_after_click`)."""

    # What the host (`BaseBusinessAction`) gives, declared here as an interface would be.
    ui_extractors: "InstagramUIExtractors"
    logger: Any
    automation: Any
    _is_likers_popup_open: Callable[[], bool]
    _close_likers_popup: Callable[[], bool]

    def _extract_likers_after_click(self, max_interactions: int = None,
                                    multiply_by: int = 2) -> List[str]:
        """Extract usernames from likers popup after the like-count element has been clicked.

        The reading of the Lab's `post.read_likers`.
        The likers popup must be on screen (`_likers_sheet_arrived`): without it, nothing is read and
        no scroll is made, an empty list and a warning. Every scroll of the reading drags the sheet;
        on any other screen it drags the post list under it (Pixel 6 Pro, Instagram 410: ten drags
        down a profile's posts for "0 liker(s)").
        """
        if not self._likers_sheet_arrived():
            self.logger.warning("⚠️ No likers popup on screen: no liker read, no scroll")
            return []
        if max_interactions is None:
            max_interactions = getattr(self, 'current_max_interactions', 
                                      self.default_config.get('max_interactions', 20))
        
        target_users = max_interactions * multiply_by
        
        if hasattr(self, 'current_max_interactions'):
            original_max = self.current_max_interactions
            self.current_max_interactions = target_users
            likers = self.ui_extractors.extract_usernames_from_likers_popup(
                current_max_interactions_attr=target_users,
                automation=self.automation,
                logger_instance=self.logger,
                add_initial_sleep=False
            )
            self.current_max_interactions = original_max
        else:
            likers = self.ui_extractors.extract_usernames_from_likers_popup(
                max_interactions=target_users,
                automation=self.automation,
                logger_instance=self.logger,
                add_initial_sleep=True
            )
        
        self._close_likers_popup()
        return likers

    def _likers_sheet_arrived(self) -> bool:
        """Is the likers popup on screen (`_is_likers_popup_open`), within `LIKERS_SHEET_ARRIVAL_S`
        of the tap that asked for it."""
        looks = int(LIKERS_SHEET_ARRIVAL_S / LIKERS_SHEET_POLL_S) + 1
        for look in range(looks):
            if self._is_likers_popup_open():
                return True
            if look < looks - 1:
                time.sleep(LIKERS_SHEET_POLL_S)
        return False
