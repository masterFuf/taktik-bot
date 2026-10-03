"""Taktik Keyboard management for the Instagram actions.

The typing itself is the shared owner's (`SharedBaseAction._type_with_taktik_keyboard`,
`_type_text_checked`): a text goes through the Taktik Keyboard or is not typed. Pasting it
another way (`adb shell input text`, uiautomator2's `send_keys`, `set_text`) writes the whole text
at once through another keyboard, a signal no person gives; only the login still does
(`TextInputMixin._paste_when_keyboard_fails`), until Kevin decides.
"""


class TypingMixin:
    """Mixin: the Taktik Keyboard's state, through the shared owner."""

    def _is_taktik_keyboard_active(self) -> bool:
        """Check if Taktik Keyboard (ADB Keyboard) is the active IME, through the shared owner
        (which also remembers the phone's own keyboard, to give it back at the end)."""
        try:
            from taktik.core.shared.input.taktik_keyboard import is_taktik_keyboard_active

            return is_taktik_keyboard_active(self._get_device_serial())
        except Exception as e:
            self.logger.debug(f"Cannot check keyboard status: {e}")
            return False
    
    def _activate_taktik_keyboard(self) -> bool:
        """Activate Taktik Keyboard as the default IME, through the shared owner.

        It used to run its own `ime set`, a second switch that remembered nothing: the phone's
        keyboard is now remembered and given back at the end of the session in ONE place
        (`taktik.core.shared.input.taktik_keyboard`).
        """
        try:
            from taktik.core.shared.input.taktik_keyboard import activate_taktik_keyboard

            return activate_taktik_keyboard(self._get_device_serial())
        except Exception as e:
            self.logger.error(f"❌ Error activating Taktik Keyboard: {e}")
            return False
    
    def _adb_input_text(self, text: str) -> bool:
        """Paste text via 'adb shell input text': the login's rescue only
        (`TextInputMixin._paste_when_keyboard_fails`).
        
        Only supports ASCII and replaces spaces with %s (ADB convention). The text goes as ONE word
        of a list: the shared door quotes it for the phone's shell, so a `$`, a quote or a
        backslash of a password reaches `input` as typed.
        """
        try:
            device_serial = self._get_device_serial()
            self._run_adb_shell(device_serial, ["input", "text", text.replace(" ", "%s")])
            self.logger.debug(f"⌨️ Typed via adb input text ({len(text)} chars)")
            return True
        except Exception as e:
            self.logger.error(f"❌ adb input text failed: {e}")
            return False
