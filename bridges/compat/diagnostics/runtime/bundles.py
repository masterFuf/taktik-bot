"""Platform bundle factories for compat action-test diagnostics."""

from loguru import logger


class ActionBundle:
    """Holds diagnostic action instances grouped by family."""


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


def create_tiktok_device_facade(raw_device):
    from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade

    return DeviceFacade(raw_device)


def build_tiktok_action_bundle(device_facade):
    """Instantiate TikTok atomic action classes for compat diagnostics."""
    from taktik.core.social_media.tiktok.actions.atomic.click_actions import ClickActions
    from taktik.core.social_media.tiktok.actions.atomic.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions
    from taktik.core.social_media.tiktok.actions.atomic.popup_actions import PopupActions
    from taktik.core.social_media.tiktok.actions.atomic.popup_detector import PopupDetector
    from taktik.core.social_media.tiktok.actions.atomic.scroll_actions import ScrollActions
    from taktik.core.social_media.tiktok.actions.atomic.search_actions import SearchActions
    from taktik.core.social_media.tiktok.actions.atomic.video_actions import VideoActions
    from taktik.core.social_media.tiktok.actions.atomic.video_detector import VideoDetector

    logger.info("Building TikTok action bundle...")
    bundle = ActionBundle()
    bundle.device = device_facade
    bundle.nav = NavigationActions(device_facade)
    bundle.detection = DetectionActions(device_facade)
    bundle.click = ClickActions(device_facade)
    bundle.popup = PopupActions(device_facade)
    bundle.popup_detector = PopupDetector(device_facade)
    bundle.scroll = ScrollActions(device_facade)
    bundle.search = SearchActions(device_facade)
    bundle.video = VideoActions(device_facade)
    bundle.video_detector = VideoDetector(device_facade)
    logger.info("TikTok action bundle ready")
    return bundle


__all__ = [
    "build_instagram_action_bundle",
    "build_tiktok_action_bundle",
    "create_instagram_device_facade",
    "create_tiktok_device_facade",
]

