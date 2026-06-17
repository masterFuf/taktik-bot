from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class TextInputSelectors:
    """Sélecteurs pour les champs de saisie de texte."""

    # === Comment field — langue-dependant (overlay locales/) ===
    _comment_field_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[@resource-id="com.instagram.android:id/comment_box_text"]',
        '//*[@resource-id="com.instagram.android:id/inline_compose_box"]',
        '//*[contains(@resource-id, "comment_box")]',
        # IT/ES hints absents du vocabulaire FR/EN -> restent neutres.
        '//*[contains(@hint, "Aggiungi un commento")]',
        '//*[contains(@hint, "Añade un comentario")]',
        '//*[contains(@resource-id, "comment_edittext")]',
        '//android.widget.EditText[contains(@resource-id, "comment")]',
        '//android.widget.EditText[@focused="true"]',
        '//android.widget.EditText[@clickable="true"]',
        '//android.widget.EditText',
    ])

    @property
    def comment_field_selectors(self) -> List[str]:
        return self._comment_field_selectors_base + L("text_input.comment_field_selectors")

    # === Caption field — langue-dependant (overlay locales/) ===
    _caption_field_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/caption_text_view"]',
        '//*[contains(@resource-id, "caption")]'
    ])

    @property
    def caption_field_selectors(self) -> List[str]:
        return self._caption_field_selectors_base + L("text_input.caption_field_selectors")

    # === Bio field — langue-dependant (overlay locales/) ===
    _bio_field_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bio"]',
        '//*[contains(@resource-id, "biography")]'
    ])

    @property
    def bio_field_selectors(self) -> List[str]:
        return self._bio_field_selectors_base + L("text_input.bio_field_selectors")

    # === Message field (DM) — neutre ("Message"/"Aa" identiques EN/FR) ===
    message_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]',
        '//*[contains(@hint, "Message")]',
        '//*[contains(@hint, "Aa")]',
        '//*[contains(@resource-id, "composer_edittext")]'
    ])

    # === Send button (DM) — langue-dependant (overlay locales/) ===
    _send_button_selectors_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
        '//*[contains(@resource-id, "send")]'
    ])

    @property
    def send_button_selectors(self) -> List[str]:
        return self._send_button_selectors_base + L("text_input.send_button_selectors")

TEXT_INPUT_SELECTORS = TextInputSelectors()
