"""Instagram app-language change workflow.

Drives the UI from the home/profile state to the target app language:

    Profile tab -> "Options" -> settings list -> "Language and translations"
    -> "Set language" -> app language picker -> pick the target by NATIVE name.

Reaching the settings screen reuses the proven logout navigation selectors
(``AUTH_SELECTORS.profile_tab_button`` / ``profile_options_button``); the
language-specific path uses ``SETTINGS_SELECTORS``. No selector literal lives in
this workflow (AGENTS invariant): everything is read from the centralized
catalogs and the locale overlay. The final language row is matched by its NATIVE
label (e.g. "English", "Français (France)"), which is identical in every UI
language, so the selection is robust whatever the current app language is.

Live step narration is emitted through an OPTIONAL injected ``notifier`` callback
(Dependency Inversion: this core workflow never imports the bridge layer). It is a
no-op when run standalone.
"""

import time
from typing import Any, Callable, Dict, Optional

from loguru import logger

from ....ui.selectors.shell.auth import AUTH_SELECTORS
from ....ui.selectors.flows.settings import SETTINGS_SELECTORS, APP_LANGUAGE_NATIVE_NAMES
from ....ui.language import detect_and_optimize
from taktik.core.shared.behavior.gesture_primitives import human_scroll_raw


StepNotifier = Callable[..., None]


class ChangeLanguageWorkflow:
    """Workflow de changement de langue de l'application Instagram."""

    def __init__(self, device, device_id: str, notifier: Optional[StepNotifier] = None):
        self.device = device
        self.device_id = device_id
        self._notify_cb = notifier
        self.logger = logger.bind(module="instagram-change-language")

        self.auth_selectors = AUTH_SELECTORS
        self.settings_selectors = SETTINGS_SELECTORS

    # ------------------------------------------------------------------
    # Step narration (no-op when no notifier is injected / standalone run)
    # ------------------------------------------------------------------
    def _notify(self, step: str, status: str, message: str = "", **extra: Any) -> None:
        if self._notify_cb is None:
            return
        try:
            self._notify_cb(step=step, status=status, message=message, **extra)
        except Exception as exc:  # narration must never break the flow
            self.logger.debug(f"step notifier failed: {exc}")

    # ------------------------------------------------------------------
    # Low-level UI helpers (mirror InstagramLogout)
    # ------------------------------------------------------------------
    def _find_element(self, selectors: list):
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element
            except Exception:
                continue
        return None

    def _click_first_match(self, selectors: list, name: str) -> bool:
        element = self._find_element(selectors)
        if element is None:
            return False
        try:
            element.click()
            self.logger.success(f"Clicked '{name}'")
            return True
        except Exception as exc:
            self.logger.error(f"Click on '{name}' failed: {exc}")
            return False

    def _element_exists(self, selectors: list) -> bool:
        return self._find_element(selectors) is not None

    def _scroll_down(self, times: int = 1) -> None:
        """Scroll down the settings list (humanized controlled scroll)."""
        for _ in range(times):
            try:
                human_scroll_raw(self.device, "down", distance_ratio=0.5)
                time.sleep(0.6)
            except Exception as exc:
                self.logger.warning(f"Swipe failed: {exc}")
                break

    def _scroll_until_present(self, selectors: list, max_scrolls: int) -> bool:
        """Scroll the current list until an element matches, or give up."""
        for attempt in range(max_scrolls + 1):
            if self._element_exists(selectors):
                return True
            if attempt < max_scrolls:
                self._scroll_down(1)
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(self, *, language: str) -> Dict[str, Any]:
        """Change the Instagram app language.

        Args:
            language: stable language code (e.g. ``"en"``, ``"fr-FR"``). See
                ``APP_LANGUAGE_NATIVE_NAMES`` for the supported set.

        Returns:
            ``{'success': bool, 'message': str, 'error_type': Optional[str],
               'language': str, 'native_name': Optional[str]}``
        """
        result: Dict[str, Any] = {
            'success': False,
            'message': '',
            'error_type': None,
            'language': language,
            'native_name': None,
        }

        native_name = APP_LANGUAGE_NATIVE_NAMES.get(language)
        if not native_name:
            result['message'] = f"Unsupported language code: {language}"
            result['error_type'] = 'unsupported_language'
            self.logger.error(result['message'])
            self._notify('validate', 'failed', result['message'])
            return result
        result['native_name'] = native_name

        self.logger.info(f"Starting change-language workflow -> {native_name} ({language})")

        # Detect the current app language so the FR/EN path selectors are optimized.
        try:
            detect_and_optimize(self.device)
        except Exception as exc:
            self.logger.debug(f"language detection skipped: {exc}")

        # 1) Own profile
        self._notify('open_profile', 'running', 'Opening profile')
        if not self._click_first_match(self.auth_selectors.profile_tab_button, 'Profile tab'):
            return self._fail(result, 'Profile tab not found', 'profile_tab_not_found', 'open_profile')
        time.sleep(2)
        self._notify('open_profile', 'done')

        # 2) Options menu (Settings and activity)
        self._notify('open_options', 'running', 'Opening the settings menu')
        if not self._click_first_match(self.auth_selectors.profile_options_button, 'Options menu'):
            return self._fail(result, 'Options menu not found on profile', 'options_menu_not_found', 'open_options')
        time.sleep(2)
        self._notify('open_options', 'done')

        # 3) "Language and translations" row (scroll the settings list to reach it)
        self._notify('open_language_settings', 'running', 'Opening Language and translations')
        rows = self.settings_selectors.language_and_translations_row
        if not self._scroll_until_present(rows, max_scrolls=8):
            return self._fail(result, 'Language and translations row not found', 'language_settings_not_found', 'open_language_settings')
        if not self._click_first_match(rows, 'Language and translations'):
            return self._fail(result, 'Could not open Language and translations', 'language_settings_click_failed', 'open_language_settings')
        time.sleep(1.5)
        self._notify('open_language_settings', 'done')

        # 4) "Set language" -> opens the app language picker
        self._notify('open_picker', 'running', 'Opening the language picker')
        if not self._click_first_match(self.settings_selectors.set_language_row, 'Set language'):
            return self._fail(result, 'Set language row not found', 'set_language_not_found', 'open_picker')
        time.sleep(1.5)
        if not self._element_exists(self.settings_selectors.language_picker_indicators):
            return self._fail(result, 'Language picker did not open', 'picker_not_opened', 'open_picker')
        self._notify('open_picker', 'done')

        # 5) Pick the target language by its NATIVE name (language-independent)
        self._notify('select_language', 'running', f"Selecting {native_name}",
                     language=language, native_name=native_name)
        target = self.settings_selectors.language_row_for(native_name)
        if not self._scroll_until_present(target, max_scrolls=15):
            return self._fail(result, f"Language not found in picker: {native_name}",
                              'language_not_in_picker', 'select_language')
        if not self._click_first_match(target, f"Language {native_name}"):
            return self._fail(result, f"Could not tap language: {native_name}",
                              'language_tap_failed', 'select_language')
        # Give Instagram time to apply the language and reload the UI.
        time.sleep(3)

        result['success'] = True
        result['message'] = f"App language set to {native_name}"
        self.logger.success(result['message'])
        self._notify('select_language', 'done', result['message'],
                     language=language, native_name=native_name)
        self._notify('done', 'done', result['message'],
                     language=language, native_name=native_name)
        return result

    def _fail(self, result: Dict[str, Any], message: str, error_type: str, step: str) -> Dict[str, Any]:
        result['message'] = message
        result['error_type'] = error_type
        self.logger.error(message)
        self._notify(step, 'failed', message)
        return result
