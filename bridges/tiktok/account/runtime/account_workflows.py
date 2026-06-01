"""Workflow adapters facade for TikTok account bridge actions."""

from bridges.tiktok.account.runtime.account_login import TikTokAccountLoginMixin
from bridges.tiktok.account.runtime.account_logout import TikTokAccountLogoutMixin
from bridges.tiktok.account.runtime.account_register import TikTokAccountRegisterMixin


class TikTokAccountWorkflowMixin(
    TikTokAccountLoginMixin,
    TikTokAccountLogoutMixin,
    TikTokAccountRegisterMixin,
):
    """Dispatch account bridge payloads to TikTok core workflows."""


__all__ = ["TikTokAccountWorkflowMixin"]
