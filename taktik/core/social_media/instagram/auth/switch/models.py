"""Data models for the account-switch process."""

from typing import List, Optional


class SwitchResult:
    """Result of an account-switch attempt."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        error_type: Optional[str] = None,
        switched_to: Optional[str] = None,
        relogin_required: bool = False,
        detected_accounts: Optional[List[str]] = None,
        requested_username: Optional[str] = None,
        previous_username: Optional[str] = None,
        active_username: Optional[str] = None,
        already_active: bool = False,
        attempts: int = 0,
        failure_stage: Optional[str] = None,
        failure_category: Optional[str] = None,
        state_known: bool = False,
    ):
        self.success = success
        self.message = message
        self.error_type = error_type
        # Username we tried to switch to (without the leading '@').
        self.switched_to = switched_to
        # True when the target account is connected but its session is NOT saved: Instagram
        # shows the password screen, so the switch can't complete without re-login. The front
        # then routes to the Login sub-view pre-filled with `switched_to`.
        self.relogin_required = relogin_required
        # Usernames seen on the account picker during the switch (device-connected accounts),
        # so the front can refresh its list.
        self.detected_accounts = detected_accounts or []
        self.requested_username = requested_username
        self.previous_username = previous_username
        self.active_username = active_username
        self.already_active = already_active
        self.attempts = attempts
        self.failure_stage = failure_stage
        self.failure_category = failure_category
        self.state_known = state_known

    def __repr__(self):
        return (
            f"SwitchResult(success={self.success}, switched_to='{self.switched_to}', "
            f"relogin_required={self.relogin_required})"
        )
