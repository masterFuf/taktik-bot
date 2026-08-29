"""Shared profile data extraction for TikTok workflows.

Provides a function that extracts profile data (username, stats, bio, website,
verified, private) from the current profile screen using raw uiautomator2 device calls.

Used by both ScrapingWorkflow (enrichment) and ProfileDataMixin (followers).
"""

from typing import Dict, Any, Optional

from ....core.utils import parse_count, first_matching, first_text
from .....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from .....ui.labels import classify_profile_stat_label


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

        # Read through the SELECTOR LIST, not through a resource-id pulled out of it. The
        # catalogue writes its anchors as `contains(@resource-id, ":id/…")`, which the id
        # extractor cannot parse — so every read below took an `if rid:` false branch and this
        # function returned its defaults, on both app versions, since ~March 2026. It is the same
        # idiom `profile_actions.get_profile_info` already uses correctly on the same screen.
        # --- Username ---
        username = first_text(raw_device, PROFILE_SELECTORS.username)
        if username:
            data['username'] = username.replace('@', '').strip()

        # --- Display name ---
        data['display_name'] = first_text(raw_device, PROFILE_SELECTORS.display_name)

        # --- Stats (followers / following / likes) ---
        stat_counts = first_matching(raw_device, PROFILE_SELECTORS.stat_value)
        stat_labels = first_matching(raw_device, PROFILE_SELECTORS.stat_label)
        for i in range(min(len(stat_counts), len(stat_labels))):
            try:
                count_text = stat_counts[i].text or '0'
                label_text = stat_labels[i].text or ''
                count = parse_count(count_text)
                # Same classification as `profile_actions` — shared, and localized:
                # comparing against English words made every count zero on a
                # French phone, with no error to show for it.
                stat = classify_profile_stat_label(label_text)
                if stat == 'following':
                    data['following_count'] = count
                elif stat == 'followers':
                    data['followers_count'] = count
                elif stat == 'likes':
                    data['likes_count'] = count
            except Exception:
                pass

        # --- Bio (catalogue selector, or fallback: long button text) ---
        bio_text = first_text(raw_device, PROFILE_SELECTORS.bio_text)
        if len(bio_text) > 3:
            data['bio'] = bio_text

        if not data['bio']:
            # Fallback: look for buttons with long text (bio area)
            bio_buttons = raw_device(**PROFILE_SELECTORS.bio_button_fallback_selector)
            for i in range(bio_buttons.count):
                try:
                    text = bio_buttons[i].get_text() or ''
                    if '\n' in text or len(text) > 50:
                        data['bio'] = text
                        break
                except Exception:
                    pass

        # --- Website ---
        link_elems = raw_device(textContains=PROFILE_SELECTORS.website_text_probe)
        if link_elems.exists:
            try:
                data['website'] = link_elems[0].get_text()
            except Exception:
                pass

        # --- Verified / private ---
        #
        # Through the CATALOGUE, not through the two English words this used to hardcode. Those
        # two reads (`descriptionContains="Verified"`, `textContains="private"`) were the last
        # raw strings on this screen, and both were dead: nothing on a TikTok profile carries the
        # word "verified" in any attribute, and a French phone shows "privé", so `is_verified`
        # and `is_private` were False for every profile the bot has ever saved — a filter that
        # skips private or verified accounts had nothing to act on.
        data['is_verified'] = bool(first_matching(raw_device, PROFILE_SELECTORS.verified_badge))
        data['is_private'] = bool(first_matching(raw_device, PROFILE_SELECTORS.private_indicator))

        return data

    except Exception:
        return None
