"""Shared profile data extraction for TikTok workflows.

Provides a function that extracts profile data (username, stats, bio, website,
verified, private) from the current profile screen using raw uiautomator2 device calls.

Used by both ScrapingWorkflow (enrichment) and ProfileDataMixin (followers).
"""

from typing import Dict, Any, Optional

from ....core.utils import parse_count, extract_resource_id
from ....ui.selectors import PROFILE_SELECTORS


def extract_profile_from_screen(raw_device, username: str = '') -> Optional[Dict[str, Any]]:
    """Extract profile data from the currently visible profile screen.

    Args:
        raw_device: A raw uiautomator2 device (not a DeviceFacade).
        username: Pre-known username (fallback if not found on screen).

    Returns:
        Dict with profile data, or None on error.
    """
    try:
        data: Dict[str, Any] = {
            'username': username,
            'display_name': '',
            'followers_count': 0,
            'following_count': 0,
            'likes_count': 0,
            'posts_count': 0,
            'bio': '',
            'website': '',
            'is_private': False,
            'is_verified': False,
            'is_enriched': True,
        }

        # --- Username ---
        username_rid = extract_resource_id(PROFILE_SELECTORS.username)
        if username_rid:
            username_elem = raw_device(resourceId=username_rid)
            if username_elem.exists:
                data['username'] = username_elem.get_text().replace('@', '').strip()

        # --- Display name ---
        display_rid = extract_resource_id(PROFILE_SELECTORS.display_name)
        if display_rid:
            display_elem = raw_device(resourceId=display_rid)
            if display_elem.exists:
                data['display_name'] = display_elem.get_text() or ''

        # --- Stats (followers / following / likes) ---
        stat_count_rid = extract_resource_id(PROFILE_SELECTORS.stat_value)
        stat_label_rid = extract_resource_id(PROFILE_SELECTORS.stat_label)
        if stat_count_rid and stat_label_rid:
            stat_counts = raw_device(resourceId=stat_count_rid)
            stat_labels = raw_device(resourceId=stat_label_rid)
            if stat_counts.exists and stat_labels.exists:
                for i in range(min(stat_counts.count, stat_labels.count)):
                    try:
                        count_text = stat_counts[i].get_text() or '0'
                        label_text = stat_labels[i].get_text() or ''
                        count = parse_count(count_text)
                        label_lower = label_text.lower()
                        if 'following' in label_lower:
                            data['following_count'] = count
                        elif 'follower' in label_lower:
                            data['followers_count'] = count
                        elif 'like' in label_lower:
                            data['likes_count'] = count
                    except Exception:
                        pass

        # --- Bio (qfx selector or fallback: long button text) ---
        bio_rid = extract_resource_id(PROFILE_SELECTORS.bio_text)
        if bio_rid:
            bio_elem = raw_device(resourceId=bio_rid)
            if bio_elem.exists:
                bio_text = bio_elem.get_text() or ''
                if len(bio_text) > 3:
                    data['bio'] = bio_text

        if not data['bio']:
            # Fallback: look for buttons with long text (bio area)
            bio_buttons = raw_device(className="android.widget.Button", clickable=True)
            for i in range(bio_buttons.count):
                try:
                    text = bio_buttons[i].get_text() or ''
                    if '\n' in text or len(text) > 50:
                        data['bio'] = text
                        break
                except Exception:
                    pass

        # --- Website ---
        link_elems = raw_device(textContains="http")
        if link_elems.exists:
            try:
                data['website'] = link_elems[0].get_text()
            except Exception:
                pass

        # --- Verified ---
        verified_elems = raw_device(descriptionContains="Verified")
        if verified_elems.exists:
            data['is_verified'] = True

        # --- Private ---
        private_elems = raw_device(textContains="private")
        if private_elems.exists:
            data['is_private'] = True

        return data

    except Exception:
        return None
