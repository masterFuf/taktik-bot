"""UI selectors for TikTok state detection and debugging."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class DetectionSelectors:
    """Selectors for TikTok state detection and debugging."""

    # === Détection de pages problématiques ===
    @property
    def error_message(self) -> List[str]:
        return L("detection.error_message")

    @property
    def network_error(self) -> List[str]:
        return L("detection.network_error")

    # === Détection de restrictions ===
    @property
    def rate_limit(self) -> List[str]:
        """A node saying TikTok refuses the account's actions (a toast or a dialog)."""
        return [f'//*[contains(@text, "{text}")]' for text in L("detection.rate_limit_texts")]

    @property
    def user_written_text(self) -> List[str]:
        """Nodes that carry what people wrote (caption, comment, message, bio): a refusal phrase
        read there proves nothing."""
        from ..surfaces.conversation import CONVERSATION_SELECTORS
        from ..surfaces.profile import PROFILE_SELECTORS
        from ..surfaces.video.comments import COMMENT_SELECTORS
        from ..surfaces.video.media import VIDEO_MEDIA_SELECTORS

        return [*VIDEO_MEDIA_SELECTORS.video_description, *COMMENT_SELECTORS.comment_text,
                *CONVERSATION_SELECTORS.message_text, *PROFILE_SELECTORS.bio]


DETECTION_SELECTORS = DetectionSelectors()
