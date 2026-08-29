"""TikTok app-language change.

    Profile tab -> profile menu -> "Settings and privacy" -> scroll to "Language"
      -> "App language" -> pick the target by its NATIVE name -> "Done"

Why this can work at all: the picker lists every language in its OWN spelling — `Deutsch`,
`Español`, `Čeština`, `Français`, `English (UK)`. Those labels do not change with the current UI
language, so the only step that must survive an unknown language is the one that does. Everything
before it is localized and read from the locale overlay, which holds BOTH languages when no locale
is active; that is what lets a run start from a phone whose language it has not detected.

The reason this workflow exists is not convenience. All three phones are fr-FR, so every English
entry in the TikTok catalogue was a guess until 2026-08-29 — the audit says as much. Being able to
flip the app is what turns "probably" into "measured", for the whole catalogue.

A change is confirmed by DETECTING the language afterwards, never by the tap on "Done". TikTok
returns to the feed on confirm, so the proof is available immediately and there is no excuse for
reporting the click.
"""

import time
from typing import Any, Callable, Dict, Optional

from loguru import logger

from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw
from taktik.core.shared.device.wait import find_element

from ....ui.language import detect_language, reset_detected_language
from ....ui.selectors.flows.settings import APP_LANGUAGE_NATIVE_NAMES, SETTINGS_SELECTORS
from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

StepNotifier = Callable[..., None]

#: How far to scroll looking for a row. The settings list needs about two screens, the picker
#: about one per twenty languages; both are far under this.
MAX_SCROLLS = 12


class TikTokChangeLanguageWorkflow:
    """Change the TikTok app language, and prove it changed."""

    def __init__(self, device, device_id: str = "", notifier: Optional[StepNotifier] = None):
        self.device = device
        self.device_id = device_id
        self._notify_cb = notifier
        self.logger = logger.bind(module="tiktok-change-language")
        self.settings = SETTINGS_SELECTORS

    # ------------------------------------------------------------------

    def _notify(self, step: str, status: str, message: str = "", **extra: Any) -> None:
        if self._notify_cb is None:
            return
        try:
            self._notify_cb(step=step, status=status, message=message, **extra)
        except Exception as exc:  # narration must never break the flow
            self.logger.debug(f"step notifier failed: {exc}")

    def _find(self, selectors):
        return find_element(self.device, selectors)

    def _click(self, selectors, name: str) -> bool:
        element = self._find(selectors)
        if element is None:
            self.logger.warning(f"❌ {name} introuvable")
            return False
        try:
            element.click()
            time.sleep(1.5)
            return True
        except Exception as exc:
            self.logger.warning(f"❌ {name} non cliquable: {exc}")
            return False

    def _wait_for(self, selectors, name: str, timeout: float = 8.0) -> bool:
        """Wait for an element to DRAW, not for a duration.

        A fixed sleep after a tap is the trap that has cost the most time on this codebase: the
        profile takes about three seconds to render, and reading at 1.5 s reports the burger menu
        as missing on a screen that is simply still drawing — indistinguishable, from the caller's
        side, from a tap that did nothing.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._find(selectors) is not None:
                return True
            time.sleep(0.4)
        self.logger.warning(f"❌ {name} jamais apparu en {timeout:.0f}s")
        return False

    def _scroll_to(self, selectors, name: str) -> bool:
        """Scroll until `selectors` resolves. Returns False rather than scrolling forever."""
        for attempt in range(MAX_SCROLLS):
            if self._find(selectors) is not None:
                if attempt:
                    self.logger.debug(f"{name} trouvé après {attempt} défilement(s)")
                return True
            human_scroll_raw(self.device, direction="down")
            time.sleep(0.9)
        self.logger.warning(f"❌ {name} jamais atteint après {MAX_SCROLLS} défilements")
        return False

    # ------------------------------------------------------------------

    def run(self, target_language: str) -> Dict[str, Any]:
        """Switch the app to `target_language` ('fr', 'en', 'en-US', ...).

        Returns a result dict carrying the language BEFORE and AFTER, so a caller can tell
        "changed" from "was already there" — two outcomes that both look like success.
        """
        native_name = APP_LANGUAGE_NATIVE_NAMES.get(target_language)
        result: Dict[str, Any] = {
            "success": False,
            "target": target_language,
            "native_name": native_name,
            "language_before": None,
            "language_after": None,
            "already_set": False,
            "error": None,
            "step": "start",
        }

        if not native_name:
            known = ", ".join(sorted(APP_LANGUAGE_NATIVE_NAMES))
            return self._fail(result, f"Unknown target language {target_language!r} (known: {known})",
                              "unknown_language")

        reset_detected_language()
        before = detect_language(self.device)
        result["language_before"] = before
        self.logger.info(f"🌐 Langue actuelle: {before} → cible: {target_language} ({native_name})")
        self._notify("detect", "done", f"current={before}")

        # Not a shortcut for its own sake: walking the settings to re-pick the language already
        # in use is four screens of device time for no change, and it is the common case when a
        # caller sets a language defensively at session start.
        if before == _base_language(target_language):
            result.update(success=True, already_set=True, language_after=before, step="already_set")
            self.logger.info("🌐 Déjà dans la langue demandée — rien à faire")
            return result

        if not self._open_settings():
            return self._fail(result, "Could not reach Settings and privacy", "settings_unreachable")

        result["step"] = "language_screen"
        if not self._scroll_to(self.settings.language_row, "la ligne « Langue »"):
            return self._fail(result, "Language row never appeared in settings", "language_row_not_found")
        if not self._click(self.settings.language_row, "la ligne « Langue »"):
            return self._fail(result, "Could not open the Language screen", "language_row_click_failed")

        result["step"] = "picker"
        if not self._click(self.settings.app_language_row, "la ligne « Langue de l'application »"):
            return self._fail(result, "Could not open the app language picker", "picker_not_opened")
        time.sleep(1.5)
        if self._find(self.settings.picker_indicator) is None:
            return self._fail(result, "The app language picker did not open", "picker_not_opened")

        result["step"] = "select"
        row = self.settings.language_row_for_native_name(native_name)
        if not self._scroll_to(row, f"la langue « {native_name} »"):
            return self._fail(result, f"Language not offered by the picker: {native_name}",
                              "language_not_in_picker")
        if not self._click(row, f"la langue « {native_name} »"):
            return self._fail(result, f"Could not select {native_name}", "language_click_failed")

        result["step"] = "confirm"
        if not self._click(self.settings.picker_confirm_button, "le bouton de validation"):
            return self._fail(result, "Could not confirm the language change", "confirm_failed")

        # The app reloads its whole UI here and drops back to the feed.
        time.sleep(5.0)
        reset_detected_language()
        after = detect_language(self.device)
        result["language_after"] = after
        result["step"] = "verify"

        # The outcome, not the click. A confirmed tap on a picker that did not apply looks
        # exactly like a successful change from the caller's side.
        if after != _base_language(target_language):
            return self._fail(
                result,
                f"Confirmed, but the app still reads as {after!r} instead of {target_language!r}",
                "language_not_applied",
            )

        result["success"] = True
        self.logger.success(f"🌐 Langue changée: {before} → {after}")
        self._notify("verify", "done", f"{before} -> {after}")
        return result

    # ------------------------------------------------------------------

    def _open_settings(self) -> bool:
        """Profile tab -> profile menu -> Settings and privacy."""
        self._notify("open_settings", "running")

        # Twice, because a tap on the profile tab can land without navigating — the feed swallows
        # it while a video is mid-transition, and the tap reports success either way. Observed on
        # device: the same call worked on its own and failed straight after a probe left the phone
        # on a playing video. The arrival is what is checked, not the tap.
        for attempt in range(2):
            if not self._click(NAVIGATION_SELECTORS.profile_tab, "l'onglet Profil"):
                return False
            if self._wait_for(PROFILE_SELECTORS.profile_menu_button, "le menu du profil", timeout=6.0):
                break
            if attempt == 0:
                self.logger.info("↻ L'onglet Profil n'a pas navigué — nouvelle tentative")
                time.sleep(1.5)
        else:
            return False

        if not self._click(PROFILE_SELECTORS.profile_menu_button, "le menu du profil"):
            return False
        time.sleep(1.5)

        # The row sits at the bottom of the menu; on a short screen it needs a scroll.
        if not self._scroll_to(self.settings.settings_and_privacy_row, "« Paramètres et confidentialité »"):
            return False
        return self._click(self.settings.settings_and_privacy_row, "« Paramètres et confidentialité »")

    def _fail(self, result: Dict[str, Any], message: str, error_type: str) -> Dict[str, Any]:
        result["error"] = message
        result["error_type"] = error_type
        self.logger.error(f"❌ {message}")
        self._notify(result.get("step", "unknown"), "error", message)
        return result


def _base_language(code: str) -> str:
    """'en-GB' -> 'en'. `detect_language` answers in base codes, the picker in regional ones."""
    return (code or "").split("-")[0].lower()


__all__ = ["TikTokChangeLanguageWorkflow", "APP_LANGUAGE_NATIVE_NAMES"]
