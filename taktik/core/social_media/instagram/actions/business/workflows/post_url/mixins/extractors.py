"""Liker extraction and UI delegation methods for post_url workflow."""

import re
import time
from typing import Dict, List, Any, Optional


class PostUrlExtractorsMixin:
    """Mixin: extract likers from posts, find matching posts, delegate to ui_extractors."""
    
    def _open_first_post_in_grid(self) -> bool:
        try:
            first_post = self.device.xpath(self.post_selectors.first_post_grid)
            if first_post.exists:
                self.logger.debug("Opening first post")
                first_post.click()
                time.sleep(3)
                return True
            else:
                self.logger.error("First post not found")
                return False
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    # _extract_likers_from_current_post, _extract_likers_from_regular_post,
    # _extract_likers_from_reel, _interact_with_user, _get_filter_criteria_from_config,
    # _determine_interactions_from_config, etc.
    # are all inherited from LikersWorkflowBase / BaseBusinessAction — no wrappers needed.
    
