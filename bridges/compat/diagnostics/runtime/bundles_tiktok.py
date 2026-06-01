"""TikTok bundle factories for compat action-test diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.runtime.action_bundle import ActionBundle


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


__all__ = ["build_tiktok_action_bundle", "create_tiktok_device_facade"]

