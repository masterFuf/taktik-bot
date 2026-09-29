"""Workflow runner facade for the Instagram account bridge."""

from __future__ import annotations

from bridges.instagram.account.language import AccountChangeLanguageRunnerMixin
from bridges.instagram.account.launch import AccountLaunchMixin
from bridges.instagram.account.login import AccountLoginRunnerMixin
from bridges.instagram.account.logout import AccountLogoutRunnerMixin
from bridges.instagram.account.register import AccountRegisterRunnerMixin
from bridges.instagram.account.switch import AccountSwitchRunnerMixin


class AccountWorkflowRunnerMixin(
    AccountLoginRunnerMixin,
    AccountRegisterRunnerMixin,
    AccountLogoutRunnerMixin,
    AccountChangeLanguageRunnerMixin,
    AccountSwitchRunnerMixin,
    AccountLaunchMixin,
):
    """Run Instagram account workflows and emit bridge JSON events."""


__all__ = ["AccountWorkflowRunnerMixin"]
