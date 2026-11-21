"""Shared profile data extraction for TikTok workflows.

Provides a function that extracts profile data (username, stats, bio, website,
verified, private) from the current profile screen using raw uiautomator2 device calls.

Used by both ScrapingWorkflow (enrichment) and ProfileDataMixin (followers).
"""

from typing import Dict, Any, Optional

from taktik.core.shared.text import handle_from_screen_text

from taktik.core.social_media.tiktok.actions.base.utils import first_matching, first_text
from taktik.core.social_media.tiktok.services.profile.profile_actions import read_profile_stats
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


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
            # A counter the screen does not show stays None (unknown), never 0.
            'followers_count': None,
            'following_count': None,
            'likes_count': None,
            'posts_count': None,  # never read here: unknown
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
        # --- Username --- (a nickname read in its place keeps the known handle)
        handle = handle_from_screen_text(first_text(raw_device, PROFILE_SELECTORS.username), 'tiktok')
        if handle:
            data['username'] = handle

        # --- Display name ---
        data['display_name'] = first_text(raw_device, PROFILE_SELECTORS.display_name)

        # --- Stats (followers / following / likes) ---
        data.update(read_profile_stats(raw_device))

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
