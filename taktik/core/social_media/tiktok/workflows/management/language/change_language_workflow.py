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

from ....services.navigation.reset import return_to_tiktok_shell

from ....ui.language import detect_language, reset_detected_language
from ....ui.selectors.flows.settings import APP_LANGUAGE_NATIVE_NAMES, SETTINGS_SELECTORS
from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS

StepNotifier = Callable[..., None]

#: How far to scroll looking for a row. Measured 2026-08-30 on a clean round trip: the Language
#: row comes up after 7 scrolls going to English and 6 coming back, the picker after 1.
#:
#: Raised from 12 because that margin is thinner than it reads. The English settings list is flat
#: and Language sits about twenty-five rows down, and this loop spends attempts on things that are
#: not distance -- a modal costs one each time it is dismissed, and a run that starts from a screen
#: other than the shell starts further away. One run did exhaust it and report "Language row never
#: appeared in settings", which reads as "TikTok moved the row" when the row was there all along.
#: A ceiling is not an expectation: the loop returns the moment it finds the row, so a wider one
#: only ever costs time on a failure that was going to fail anyway.
MAX_SCROLLS = 18


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

    def _is_tappable(self, element) -> bool:
        """Is the element clear of the screen edges, or merely present?

        The settings screens are Jetpack Compose: NOTHING in them reports `clickable="true"`, so
        the climb-to-the-tappable-ancestor anchor used everywhere else resolves to nothing and the
        only option is tapping the label's own centre. That makes its position part of whether the
        tap can land at all.

        Measured 2026-08-30: « Contenu et affichage » sitting at y=2258 on a 2400 px screen — under
        the system navigation bar — was found by the selector and tapped, and nothing happened.
        The same row, scrolled up to y=1561, opened on the first tap. A check that only asks
        "is it there?" reports that miss as a successful click.
        """
        try:
            bounds = element.get().bounds
            height = self.device.window_size()[1]
        except Exception:
            return True  # cannot measure -> do not block the flow on the check itself
        top, bottom = bounds[1], bounds[3]
        return height * 0.10 < top and bottom < height * 0.82

    def _scroll_to(self, selectors, name: str, max_scrolls: int = MAX_SCROLLS) -> bool:
        """Scroll until `selectors` resolves. Returns False rather than scrolling forever.

        A modal is checked for on the way. Measured 2026-08-30: after a pass through the privacy
        settings TikTok raises « Vérifier à nouveau dans 2 semaines ? », and this scrolled twelve
        times against it before declaring the Language row missing — a report that says "the row
        is gone" when the truth is "nothing on this screen is reachable". Scrolling under a modal
        also lands taps on whatever is behind it: the run ended inside a Downloads sub-screen.
        """
        for attempt in range(max_scrolls):
            element = self._find(selectors)
            if element is not None and self._is_tappable(element):
                if attempt:
                    self.logger.debug(f"{name} trouvé après {attempt} défilement(s)")
                return True
            if element is not None:
                self.logger.debug(f"{name} est à l'écran mais hors de portée d'un tap — on continue")
            if attempt and self._dismiss_blocking_popup():
                continue  # re-read the screen before spending another scroll on it
            human_scroll_raw(self.device, direction="down")
            time.sleep(0.9)
        self.logger.warning(f"❌ {name} jamais atteint après {max_scrolls} défilements")
        return False

    def _dismiss_blocking_popup(self) -> bool:
        """Close whatever modal TikTok raised, through the shared popup actions.

        Reused rather than respelled: `PopupActions.close_popup` already knows every dismissal
        this app uses, and a second answer here would miss the next one it learns.
        """
        try:
            from ....actions.atomic.popup_actions import PopupActions

            if PopupActions(self.device).close_popup():
                self.logger.info("↻ Popup écartée avant de continuer")
                time.sleep(1.0)
                return True
        except Exception as exc:
            self.logger.debug(f"popup check failed: {exc}")
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
            # This branch touches nothing, so it also FIXES nothing: it hands on whatever screen
            # it was given. Cheap insurance, since a caller that sets a language defensively at
            # session start lands here almost every time.
            self._leave_on_the_shell()
            return result

        if not self._open_settings():
            return self._fail(result, "Could not reach Settings and privacy", "settings_unreachable")

        result["step"] = "language_screen"
        if not self._reach_language_row():
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
        # Applying the language reloads the whole UI and usually drops back to the feed on its
        # own -- usually is not a contract, and the next workflow inherits whatever this leaves.
        self._leave_on_the_shell()
        return result

    # ------------------------------------------------------------------

    def _open_settings(self) -> bool:
        """Profile tab -> profile menu -> Settings and privacy."""
        self._notify("open_settings", "running")

        # Before anything: a modal left over from a previous pass swallows the tab tap too.
        self._dismiss_blocking_popup()

        # And the bottom bar has to exist before a tab can be tapped. A settings sub-screen is a
        # full-screen page with NO bar, so tapping the profile tab from inside one taps nothing —
        # and `_wait_for` then reports the profile menu as missing, which reads as "the menu is
        # gone" rather than "we are not where tabs live". Measured 2026-08-30: started from a
        # settings sub-screen, this walked twelve scrolls on a Profile-views page and declared the
        # Language row absent. Same failure, same fix, as the navigation reset earlier today.
        return_to_tiktok_shell(self.device, logger=self.logger)

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

    def _reach_language_row(self) -> bool:
        """Get the « Langue » row on screen, opening its section when it is nested.

        On 46.6.3 the settings list holds eight rows and Language is NOT one of them: it lives
        behind « Contenu et affichage ». This used to scroll the top-level list twelve times and
        then report "Language row never appeared in settings" — which reads as "TikTok moved it"
        when the truth was "we never opened the drawer".

        Tried flat FIRST, and only then through the section, because that ordering costs nothing
        on a build that does show it at top level and is what keeps this working on 43.1.4
        without a version test.
        """
        # A FULL pass first, not a short one. The English list is flat and long — Language sits
        # about twenty-five rows down, after the "Content & Display" heading — so a shortened
        # look gives up before reaching it and then goes hunting for a drawer that this layout
        # does not have. Measured on both languages 2026-08-30.
        if self._scroll_to(self.settings.language_row, "la ligne « Langue »"):
            return True

        # French: same app version, same screen, NESTED. "Contenu et affichage" is a tappable row
        # that opens a sub-screen, and Language is inside it. TikTok serves two different settings
        # layouts for the same build depending on the UI language.
        self.logger.info("↻ « Langue » absente à ce niveau — ouverture de « Contenu et affichage »")
        self._scroll_to_top()
        if not self._scroll_to(self.settings.content_and_display_row, "« Contenu et affichage »"):
            return False
        if not self._click(self.settings.content_and_display_row, "« Contenu et affichage »"):
            return False
        return self._scroll_to(self.settings.language_row, "la ligne « Langue »")

    def _scroll_to_top(self) -> None:
        """Back to the top of the list, because the first pass left us at the bottom."""
        for _ in range(MAX_SCROLLS):
            human_scroll_raw(self.device, direction="up")
            time.sleep(0.5)

    def _fail(self, result: Dict[str, Any], message: str, error_type: str) -> Dict[str, Any]:
        result["error"] = message
        result["error_type"] = error_type
        self.logger.error(f"❌ {message}")
        self._notify(result.get("step", "unknown"), "error", message)
        self._leave_on_the_shell()
        return result

    def _leave_on_the_shell(self) -> None:
        """Put the phone back where tabs exist before handing control back.

        A failure can stop anywhere -- the settings list, the Language screen, the picker -- and
        a settings sub-screen is a full-screen page with NO bottom bar. Whatever runs next taps a
        tab that is not there and reports its own surface as missing, which reads as "the screen
        is gone" rather than "we are not where tabs live". Measured on 2026-08-30: three
        change-language runs chained back to back, and the third failed with
        `language_row_not_found` from a state the first two had left behind. Run on its own from a
        clean start, the same call succeeded.

        The same three calls, in the same order, pass with this in place. That is the controlled
        comparison -- nothing changed but the exit -- so the leftover screen was the cause. The
        `already_set` branch is what carried it: it touches nothing, so it hands the state on.
        """
        try:
            return_to_tiktok_shell(self.device, logger=self.logger)
        except Exception as exc:
            self.logger.debug(f"Could not return to the shell after the language run: {exc}")


def _base_language(code: str) -> str:
    """'en-GB' -> 'en'. `detect_language` answers in base codes, the picker in regional ones."""
    return (code or "").split("-")[0].lower()


__all__ = ["TikTokChangeLanguageWorkflow", "APP_LANGUAGE_NATIVE_NAMES"]
