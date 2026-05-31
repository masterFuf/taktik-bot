"""Compatibility facade for the Instagram human behavior recorder."""

from taktik.core.social_media.instagram.recorder.human_behavior_recorder import (
    ContentSampler,
    DetectionProbe,
    HumanBehaviorRecorder,
    RecordedEvent,
    ScreenDetector,
    UISnapshot,
)

__all__ = [
    "ContentSampler",
    "DetectionProbe",
    "HumanBehaviorRecorder",
    "RecordedEvent",
    "ScreenDetector",
    "UISnapshot",
]
