"""Workflow runner facade for the Instagram account bridge."""

from __future__ import annotations

from bridges.instagram.account.runtime.login import AccountLoginRunnerMixin
from bridges.instagram.account.runtime.logout import AccountLogoutRunnerMixin
from bridges.instagram.account.runtime.register import AccountRegisterRunnerMixin


class AccountWorkflowRunnerMixin(
    AccountLoginRunnerMixin,
    AccountRegisterRunnerMixin,
    AccountLogoutRunnerMixin,
):
    """Run Instagram account workflows and emit bridge JSON events."""


__all__ = ["AccountWorkflowRunnerMixin"]
