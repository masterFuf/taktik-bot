"""The app language of a Lab run, detected once the app is in the foreground.

Production detects the language after it has launched the app (`runtime_setup`, the TikTok
startup): the vocabulary lives in the app's own screens. The Lab detected it when the session
opened, which is usually before `app.launch`, with the Android launcher on screen. The dump held
none of the app's words, the answer was `unknown`, and the session never asked again: on the four
phones of 2026-09-23 every Lab action ran with the union of both languages' selectors, which
production never does (`applied: false` in every result).

The rule now: detect only when the platform's app is on screen, and while the language is still
unknown, try again around each action. A forced language (the Lab's picker) needs no screen.
Once a language is applied it is never detected again: the selector filtering it triggers is
in place and one-way, the same as in production.
"""

from typing import Callable, Optional

from taktik.core.shared.device.app_inspection import is_platform_foreground


class LabLanguage:
    """Holds the language payload of a Lab run and refreshes it while it is unknown."""

    def __init__(
        self,
        platform: str,
        device,
        detect: Callable[..., dict],
        *,
        override: Optional[str] = None,
        foreground: Callable[[object, str], bool] = is_platform_foreground,
    ) -> None:
        self._platform = platform
        self._device = device
        self._detect = detect
        self._override = override
        self._foreground = foreground
        self.payload: dict = {
            "platform": platform,
            "language": "unknown",
            "applied": False,
            "reason": "not_detected_yet",
            "timingMs": 0,
        }

    @property
    def applied(self) -> bool:
        return bool(self.payload.get("applied"))

    def refresh(self) -> dict:
        """Detect the language if it is still unknown and the app is on screen. Returns the payload.

        Costs nothing once a language is applied, and one foreground read while the app is not on
        screen: the dump is only taken when it can contain the app's words.
        """
        if self.applied:
            return self.payload
        if not self._override:
            try:
                in_front = bool(self._foreground(self._device, self._platform))
            except Exception:  # noqa: BLE001 - a diagnostic must never stop the Lab
                in_front = False
            if not in_front:
                self.payload = {**self.payload, "reason": "app_not_in_foreground"}
                return self.payload
        self.payload = self._detect(self._platform, self._device, override=self._override)
        return self.payload


__all__ = ["LabLanguage"]
