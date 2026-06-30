"""Data models for the account-switch process."""

from typing import List, Optional


class SwitchResult:
    """Résultat d'une tentative de changement de compte (switch)."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        error_type: Optional[str] = None,
        switched_to: Optional[str] = None,
        relogin_required: bool = False,
        detected_accounts: Optional[List[str]] = None,
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

    def __repr__(self):
        return (
            f"SwitchResult(success={self.success}, switched_to='{self.switched_to}', "
            f"relogin_required={self.relogin_required})"
        )
