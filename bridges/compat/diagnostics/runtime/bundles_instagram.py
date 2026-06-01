"""Instagram bundle factories for compat action-test diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.runtime.action_bundle import ActionBundle


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
    from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction

    logger.info("Building action bundle...")
    bundle = ActionBundle()
    bundle.device = device_facade
    bundle.nav = NavigationActions(device_facade)
    bundle.detection = DetectionActions(device_facade)
    bundle.click = ClickActions(device_facade)
    bundle.scroll = ScrollActions(device_facade)
    bundle.kb = TextActions(device_facade)
    bundle.comment = CommentAction(device_facade)
    bundle.popup = BaseBusinessAction(device_facade)
    logger.info("Action bundle ready")
    return bundle


__all__ = ["build_instagram_action_bundle", "create_instagram_device_facade"]

