"""Bridge keyboard facade built on top of the shared Taktik Keyboard owner."""

from loguru import logger

from taktik.core.shared.input.taktik_keyboard import (
    activate_taktik_keyboard,
    is_taktik_keyboard_active,
    type_with_taktik_keyboard,
)


class KeyboardService:
    """
    Type text on an Android device using the shared Taktik Keyboard runtime.

    The bridge keeps a thin adapter API for historical callers while the
    durable IME/ADB behavior stays owned by `taktik.core.shared.input`.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id

    def ensure_active(self) -> bool:
        """
        Ensure Taktik Keyboard is the active IME.

        Returns True if the keyboard is active or was activated successfully.
        """
        try:
            if is_taktik_keyboard_active(self.device_id):
                return True

            if not activate_taktik_keyboard(self.device_id):
                logger.warning("Could not activate Taktik Keyboard")
                return False

            logger.info("Taktik Keyboard activated")
            return True
        except Exception as exc:
            logger.error(f"Error checking/activating Taktik Keyboard: {exc}")
            return False

    def type_text(
        self,
        text: str,
        delay_mean: int = 80,
        delay_deviation: int = 30,
    ) -> bool:
        """
        Type text using Taktik Keyboard via the shared core owner.

        Args:
            text: The text to type (supports Unicode, emojis and accents).
            delay_mean: Average delay between keystrokes in ms.
            delay_deviation: Deviation around the mean in ms.

        Returns:
            True if the shared keyboard workflow succeeded.
        """
        if not text:
            return True

        try:
            if not self.ensure_active():
                return False

            return type_with_taktik_keyboard(
                self.device_id,
                text,
                delay_mean=delay_mean,
                delay_deviation=delay_deviation,
            )
        except Exception as exc:
            logger.error(f"Error using Taktik Keyboard: {exc}")
            return False


__all__ = ["KeyboardService"]
