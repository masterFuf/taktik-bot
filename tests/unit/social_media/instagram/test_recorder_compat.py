from taktik.core.social_media.instagram.recorder import human_behavior_recorder as owner_module
from taktik.core.social_media.instagram.recorder import (
    ContentSampler,
    DetectionProbe,
    HumanBehaviorRecorder,
    ScreenDetector,
)


def test_instagram_recorder_exports_owner_runtime():
    assert HumanBehaviorRecorder is owner_module.HumanBehaviorRecorder


def test_instagram_recorder_package_exports_runtime_symbols():
    assert ScreenDetector is owner_module.ScreenDetector
    assert ContentSampler is owner_module.ContentSampler
    assert DetectionProbe is owner_module.DetectionProbe
