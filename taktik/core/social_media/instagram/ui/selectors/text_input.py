from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class TextInputSelectors:
    """Sélecteurs pour les champs de saisie de texte."""
    
    # === Comment field ===
    comment_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/layout_comment_thread_edittext"]',
        '//*[contains(@hint, "Ajouter un commentaire")]',
        '//*[contains(@hint, "Add a comment")]',
        '//*[contains(@resource-id, "comment_edittext")]'
    ])
    
    # === Caption field ===
    caption_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/caption_text_view"]',
        '//*[contains(@hint, "Écrivez une légende")]',
        '//*[contains(@hint, "Write a caption")]',
        '//*[contains(@resource-id, "caption")]'
    ])
    
    # === Bio field ===
    bio_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/bio"]',
        '//*[contains(@hint, "Biographie")]',
        '//*[contains(@hint, "Bio")]',
        '//*[contains(@resource-id, "biography")]'
    ])
    
    # === Message field (DM) ===
    message_field_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]',
        '//*[contains(@hint, "Message")]',
        '//*[contains(@hint, "Aa")]',
        '//*[contains(@resource-id, "composer_edittext")]'
    ])
    
    # === Send button (DM) ===
    send_button_selectors: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/row_thread_composer_button_send"]',
        '//*[contains(@content-desc, "Envoyer")]',
        '//*[contains(@content-desc, "Send")]',
        '//*[contains(@resource-id, "send")]'
    ])

TEXT_INPUT_SELECTORS = TextInputSelectors()
