from taktik.core.recorder import HumanBehaviorRecorder
from taktik.core.recorder.recorder import ContentSampler, DetectionProbe, ScreenDetector
from taktik.core.social_media.instagram.recorder import human_behavior_recorder as owner_module


def test_core_recorder_reexports_owner_runtime():
    assert HumanBehaviorRecorder is owner_module.HumanBehaviorRecorder


def test_core_recorder_module_keeps_legacy_symbols():
    assert ScreenDetector is owner_module.ScreenDetector
    assert ContentSampler is owner_module.ContentSampler
    assert DetectionProbe is owner_module.DetectionProbe
