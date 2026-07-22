from types import SimpleNamespace

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade


def test_business_facades_share_one_session_behavior_timeline():
    raw = SimpleNamespace(
        window_size=lambda: (1080, 2280),
        info={"displayWidth": 1080, "displayHeight": 2280},
    )
    facade = object.__new__(DeviceFacade)
    facade._device = raw
    state = BehaviorSessionState(seed=17)

    business = object.__new__(BaseBusinessAction)
    business.device = facade
    business.behavior_state = state
    business._init_atomic_actions()

    assert business.behavior_state is state
    assert business.scroll_actions.behavior_state is state
    assert business.nav_actions.behavior_state is state
    assert business.click_actions.behavior_state is state

    first = business.scroll_actions._choose_advance_mode("profile_posts")
    second = business.click_actions._plan_behavior_gesture("story_tray", "hswipe")
    third = business.nav_actions._plan_behavior_gesture("story_advance", "tap")

    assert [first["index"], second["index"], third["index"]] == [1, 2, 3]
    assert state.snapshot()["gesture_count"] == 3
