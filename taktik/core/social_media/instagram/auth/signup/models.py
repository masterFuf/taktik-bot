"""Data models for the Instagram signup process."""

from typing import Optional


class SignupResult:
    """Résultat d'une étape ou du processus complet de création de compte."""

    def __init__(
        self,
        success: bool,
        message: str,
        step: str = "unknown",
        error_type: Optional[str] = None
    ):
        self.success = success
        self.message = message
        # Étape atteinte : "home", "phone_input", "email_input", "completed", ...
        self.step = step
        self.error_type = error_type

    def __repr__(self):
        return (
            f"SignupResult(success={self.success}, step='{self.step}', "
            f"message='{self.message}')"
        )
