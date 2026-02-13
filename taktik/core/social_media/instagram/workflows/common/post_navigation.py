"""Shared post navigation functions for scraping/discovery workflows.

All functions take `device` and `logger` as parameters — no class dependency.
"""

import time

from ...ui.selectors import DETECTION_SELECTORS, POST_SELECTORS, POPUP_SELECTORS
from .detection import is_in_post_view, is_likers_popup_open


def open_first_post_of_profile(device, logger=None) -> bool:
    """Open the first post in the current profile's grid."""
    try:
        posts = device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()

        if not posts:
            posts = device.xpath(POST_SELECTORS.first_post_grid).all()

        if not posts:
            if logger:
                logger.error("No posts found in grid")
            return False

        posts[0].click()
        time.sleep(3)

        if is_in_post_view(device, logger):
            if logger:
                logger.info("First post opened successfully")
            return True

        if logger:
            logger.error("Failed to open first post")
        return False

    except Exception as e:
        if logger:
            logger.error(f"Error opening first post: {e}")
        return False


def open_likers_list(device, ui_extractors, logger=None) -> bool:
    """Open the likers list by clicking on the like count element.

    Args:
        device: uiautomator2 device
        ui_extractors: InstagramUIExtractors instance (has find_like_count_element)
        logger: optional logger
    """
    try:
        like_count_element = ui_extractors.find_like_count_element(logger_instance=logger)

        if not like_count_element:
            if logger:
                logger.warning("No like counter found")
            return False

        like_count_element.click()
        time.sleep(1.5)

        if is_likers_popup_open(device, logger):
            if logger:
                logger.debug("Likers popup opened successfully")
            return True

        if logger:
            logger.warning("Could not verify likers popup opened")
        return False

    except Exception as e:
        if logger:
            logger.error(f"Error opening likers list: {e}")
        return False
