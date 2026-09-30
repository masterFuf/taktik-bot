"""Ce qui LIT l'ecran TikTok : etat, extraction, collecte. Rien ici n'agit."""

from taktik.core.social_media.tiktok.actions.atomic.detection.avatar_actions import AvatarActions
from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
from taktik.core.social_media.tiktok.actions.atomic.detection.popup_detector import PopupDetector
from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions
from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector

__all__ = [
    "AvatarActions",
    "DetectionActions",
    "PopupDetector",
    "SoundActions",
    "VideoDetector",
]
