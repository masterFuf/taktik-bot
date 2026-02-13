"""Data models for the login process."""

from typing import Optional


class LoginResult:
    """Résultat d'une tentative de login."""
    
    def __init__(
        self,
        success: bool,
        message: str,
        requires_2fa: bool = False,
        error_type: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.requires_2fa = requires_2fa
        self.error_type = error_type
    
    def __repr__(self):
        return f"LoginResult(success={self.success}, message='{self.message}')"
