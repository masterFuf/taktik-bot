"""Data models for the logout process."""

from typing import Optional


class LogoutResult:
    """Résultat d'une tentative de logout."""

    def __init__(
        self,
        success: bool,
        message: str,
        error_type: Optional[str] = None,
    ):
        self.success = success
        self.message = message
        self.error_type = error_type

    def __repr__(self):
        return f"LogoutResult(success={self.success}, message='{self.message}')"
