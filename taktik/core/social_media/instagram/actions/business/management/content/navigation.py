"""Content navigation helpers (navigate to post URL, hashtag)."""

import re
from loguru import logger
from .....utils.taktik_keyboard import run_adb_shell


def navigate_to_post_via_url(business_action, post_url: str) -> bool:
    """Navigate to an Instagram post via its URL using deep link.
    
    Args:
        business_action: A BaseBusinessAction instance (provides device, logger, etc.)
        post_url: The Instagram post URL
    """
    try:
        post_id_match = re.search(r'/p/([^/]+)/', post_url)
        if not post_id_match:
            return False
        
        post_id = post_id_match.group(1)
        
        # Use adbutils via run_adb_shell for compatibility with packaged builds
        device_serial = business_action._get_device_serial()
        deep_link_url = f'https://www.instagram.com/p/{post_id}/'
        result = run_adb_shell(device_serial, f'am start -W -a android.intent.action.VIEW -d "{deep_link_url}" com.instagram.android')
        
        if result and 'Error' not in result:
            business_action._human_like_delay('navigation')
            return True
        
    except Exception as e:
        business_action.logger.debug(f"Error navigating to post: {e}")
    
    return False


def navigate_to_hashtag(business_action, hashtag: str) -> bool:
    """Navigate to a hashtag page via search.
    
    Args:
        business_action: A BaseBusinessAction instance (provides nav_actions, device, etc.)
        hashtag: The hashtag to navigate to (without #)
    """
    try:
        if not business_action.nav_actions.navigate_to_search():
            return False
        
        search_term = f"#{hashtag}"
        if not business_action._find_and_click(business_action.detection_selectors.hashtag_search_bar_selectors, timeout=5):
            return False
        
        business_action._human_like_delay('click')
        # Use Taktik Keyboard for reliable text input
        if not business_action._type_with_taktik_keyboard(search_term):
            business_action.logger.warning("Taktik Keyboard failed, falling back to send_keys")
            business_action.device.send_keys(search_term)
        business_action._human_like_delay('typing')
        
        hashtag_result_selectors = [
            f'//*[contains(@text, "#{hashtag}")]',
            '//*[contains(@resource-id, "hashtag")]'
        ]
        
        if business_action._find_and_click(hashtag_result_selectors, timeout=5):
            business_action._human_like_delay('navigation')
            return True
        
    except Exception as e:
        business_action.logger.debug(f"Error navigating to hashtag: {e}")
    
    return False
