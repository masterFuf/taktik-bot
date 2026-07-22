"""Instagram bundle factories for compat action-test diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.runtime.action_test.action_bundle import ActionBundle


def create_instagram_device_facade(raw_device):
    from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade

    return DeviceFacade(raw_device)


def build_instagram_action_bundle(device_facade):
    """Instantiate Instagram atomic action classes for compat diagnostics."""
    from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
    from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.atomic.scroll import ScrollActions
    from taktik.core.social_media.instagram.actions.atomic.text import TextActions
    from taktik.core.social_media.instagram.actions.business.actions.comment.action import CommentAction
    from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import LikeOrchestration
    from taktik.core.social_media.instagram.actions.business.actions.story import StoryBusiness
    from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
    from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction
    from taktik.core.shared.behavior.session_state import BehaviorSessionState

    logger.info("Building action bundle...")
    behavior_state = BehaviorSessionState()
    bundle = ActionBundle()
    bundle.device = device_facade
    bundle.nav = NavigationActions(device_facade, behavior_state=behavior_state)
    bundle.detection = DetectionActions(device_facade)
    bundle.click = ClickActions(device_facade, behavior_state=behavior_state)
    bundle.scroll = ScrollActions(device_facade, behavior_state=behavior_state)
    bundle.kb = TextActions(device_facade)
    bundle.comment = CommentAction(device_facade)
    # Like orchestration carries the post-grid entry + in-viewer navigation helpers
    # (PostNavigationMixin) exercised by the profile/post Lab actions.
    bundle.like = LikeOrchestration(device_facade)
    # Engagement orchestrations (stories / feed / unfollow) exercised by the engagement.* Lab
    # actions — same production classes the workflows use, built on the warm device.
    bundle.story = StoryBusiness(device_facade)
    bundle.feed = FeedBusiness(device_facade)
    bundle.unfollow = UnfollowBusiness(device_facade)
    bundle.popup = BaseBusinessAction(device_facade)
    # The Lab bundle has no workflow SessionManager, but its production action facades still need
    # one shared per-bundle memory so repeated feed/profile probes exercise real session bursts.
    for component in (bundle.comment, bundle.like, bundle.story, bundle.feed,
                      bundle.unfollow, bundle.popup):
        component.behavior_state = behavior_state
        scroll_actions = getattr(component, "scroll_actions", None)
        if scroll_actions is not None:
            scroll_actions.behavior_state = behavior_state
        nav_actions = getattr(component, "nav_actions", None)
        if nav_actions is not None:
            nav_actions.behavior_state = behavior_state
        click_actions = getattr(component, "click_actions", None)
        if click_actions is not None:
            click_actions.behavior_state = behavior_state
    logger.info("Action bundle ready")
    return bundle


__all__ = ["build_instagram_action_bundle", "create_instagram_device_facade"]
