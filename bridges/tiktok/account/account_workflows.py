"""Workflow adapters facade for TikTok account bridge actions."""

from bridges.tiktok.account.account_launch import TikTokAccountLaunchMixin
from bridges.tiktok.account.account_login import TikTokAccountLoginMixin
from bridges.tiktok.account.account_language import TikTokAccountLanguageMixin
from bridges.tiktok.account.account_logout import TikTokAccountLogoutMixin
from bridges.tiktok.account.account_register import TikTokAccountRegisterMixin


class TikTokAccountWorkflowMixin(
    TikTokAccountLanguageMixin,
    TikTokAccountLoginMixin,
    TikTokAccountLogoutMixin,
    TikTokAccountRegisterMixin,
    TikTokAccountLaunchMixin,
):
    """Dispatch account bridge payloads to the TikTok account launcher."""


__all__ = ["TikTokAccountWorkflowMixin"]
