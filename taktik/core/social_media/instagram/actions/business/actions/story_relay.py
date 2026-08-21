"""Re-sharing someone else's story to our own, as a sequence of screen gestures.

Owns the screen work and nothing else: no database, no scheduling, no decision about which
stories are worth relaying. It reports what the app allowed, and the task above decides what
that means.

The important verdict is `unavailable`. Instagram only offers "add to my story" for a story
that MENTIONS us — for anything else the toolbar's only sharing affordance is a DM ("send the
story", confirmed on a real dump). So a missing cell is not a broken selector, it is the
product answering no, and the caller has to be able to tell the two apart. Returning it as a
distinct outcome is what lets one real run settle the question.
"""

from typing import Any, Dict

from ....actions.atomic.interaction.bottom_sheet import dismiss_share_sheet
from ...core.base_business import BaseBusinessAction


class StoryRelayBusiness(BaseBusinessAction):
    """Open a source account's story and try to push it to our own story."""

    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation=automation, module_name="story-relay")

    def open_source_story(self, source_username: str) -> Dict[str, Any]:
        """Navigate to the source profile and open its live story ring.

        Highlights are deliberately out of reach here: `click_profile_story_ring` is scoped to
        the avatar container, so an account with only "à la une" bubbles reports no story
        rather than relaying a months-old highlight.
        """
        result: Dict[str, Any] = {"opened": False, "reason": None}

        if not self.nav_actions.navigate_to_profile(source_username):
            result["reason"] = "profile_unreachable"
            return result

        if not self.detection_actions.has_unseen_profile_story():
            result["reason"] = "no_story"
            return result

        if not self.click_actions.click_profile_story_ring():
            result["reason"] = "ring_not_clickable"
            return result

        self._human_like_delay('story_load')

        if not self.detection_actions.is_story_viewer_open():
            result["reason"] = "viewer_did_not_open"
            return result

        result["opened"] = True
        return result

    def current_story_identity(self) -> Dict[str, Any]:
        """Author and posted-time of the story on screen — the relay's dedup material.

        Instagram never exposes a story id to the accessibility tree. The viewer header does
        carry the author and a coarse posted-time label ("5 h"), and the pair is stable for as
        long as that story is up, which is exactly the window the relay cares about.
        """
        metadata = self.detection_actions.get_story_viewer_metadata()
        return {
            "is_open": bool(metadata.get("is_open")),
            "is_ad": bool(metadata.get("is_ad")),
            "author": metadata.get("title"),
            "timestamp": metadata.get("timestamp"),
            "current_story": metadata.get("current_story") or 0,
            "total_stories": metadata.get("total_stories") or 0,
        }

    def push_current_story_to_mine(self) -> Dict[str, Any]:
        """Try the native re-share on the story currently open.

        Returns `status` in {'relayed', 'unavailable', 'failed'} — see the module docstring on
        why 'unavailable' is a first-class answer rather than a failure.
        """
        result: Dict[str, Any] = {"status": "failed", "reason": None}

        if not self.click_actions.open_story_share_sheet():
            result["reason"] = "share_sheet_did_not_open"
            return result

        if not self.click_actions.tap_add_to_my_story():
            # The sheet is up but carries no "add to my story" cell: this story does not
            # mention us, so Instagram does not offer the affordance at all.
            result["status"] = "unavailable"
            result["reason"] = "add_to_story_not_offered"
            # Shared verified cascade, the same one the Lab and production dismiss with: it
            # re-checks that the sheet is really gone instead of firing a blind back.
            dismiss_share_sheet(self.device, log=self.logger.debug)
            return result

        self._human_like_delay('story_load')

        if not self.publish_opened_story():
            result["reason"] = "publish_button_not_found"
            return result

        result["status"] = "relayed"
        return result

    def publish_opened_story(self) -> bool:
        """Confirm the pre-filled story editor that the re-share opened.

        Reuses the production publish selectors rather than a relay-local copy: this is the
        same "Your story" button the normal publish flow taps, and forking it would let the
        two drift the next time Instagram renames it.
        """
        from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
            CONTENT_CREATION_SELECTORS as CC,
        )

        if not self.click_actions._find_and_click(CC.story_publish_xpaths(), timeout=6):
            return False
        self._human_like_delay('story_load')
        # One-time promo Instagram shows after the first story-to-story share; harmless absent.
        self.click_actions._find_and_click(CC.story_share_promo_dismiss_xpaths(), timeout=2)
        return True

    def leave_story_viewer(self) -> bool:
        """Close the viewer if it is still up, through the production conditional close."""
        return self.click_actions.close_story_if_open(self.detection_actions)

    def advance_to_next_story(self) -> bool:
        """Move to the next slide of the same author, humanised like every other advance."""
        return self.nav_actions.navigate_to_next_story(settle=False)
