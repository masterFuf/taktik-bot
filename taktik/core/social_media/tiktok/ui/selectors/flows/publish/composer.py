"""Selectors for composing the final TikTok publish payload."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids


@dataclass
class PublishComposerSelectors:
    """Selectors for caption entry, hashtag suggestions, and final submit."""

    _caption_input_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/g19")]',
        '//android.widget.EditText[@clickable="true"][1]',
        '(//android.widget.EditText)[1]',
    ])
    _caption_input_en: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "Add a description")]',
        '//android.widget.EditText[contains(@text, "Add a description")]',
        '//android.widget.EditText[contains(@content-desc, "Add a description")]',
        '//android.widget.EditText[contains(@hint, "description")]',
        '//android.widget.EditText[contains(@hint, "Description")]',
        '//android.widget.EditText[contains(@content-desc, "Description")]',
        '//android.widget.EditText[contains(@hint, "caption")]',
    ])
    _caption_input_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "Ajouter une description")]',
        '//android.widget.EditText[contains(@text, "Ajouter une description")]',
        '//android.widget.EditText[contains(@content-desc, "Ajouter une description")]',
    ])
    _post_btn_rids: List[str] = field(default_factory=lambda: resource_ids("qrb", "post_btn"))
    _post_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Post"]',
        '//android.widget.Button[contains(@content-desc, "Post")]',
        '//android.widget.Button[@text="Post"]',
        '//android.widget.Button[contains(@text, "Post")]',
        '//android.widget.TextView[contains(@text, "Post")]',
    ])
    _post_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Publier")]',
        '//android.widget.TextView[contains(@text, "Publier")]',
    ])
    _publish_confirm_dialog_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/w4m")][contains(@text, "Publier la vid\u00e9o publiquement")]',
        '//*[contains(@text, "Publier la vid\u00e9o publiquement")]',
    ])
    _publish_confirm_dialog_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Publish video publicly")]',
    ])
    _publish_confirm_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Publier maintenant"]',
        '//android.widget.Button[contains(@text, "Publier")]',
    ])
    _publish_confirm_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Publish now")]',
    ])
    _keyboard_overlay_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/switchButton")]',
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/subtitle")]',
        '//*[contains(@resource-id, "com.alexal1.adbkeyboard:id/typingNoProgress")]',
        '//*[contains(@text, "Waiting for a job")]',
        '//*[contains(@text, "Auto-typing keyboard")]',
    ])
    _hashtag_suggestion_nodes: List[str] = field(default_factory=lambda: [
        '//*[@class="android.widget.TextView" and starts-with(@text, "#")]',
    ])
    _hashtag_suggestion_rows: List[str] = field(default_factory=lambda: [
        '(//android.view.ViewGroup[@clickable="true"][.//android.widget.TextView[starts-with(@text,"#")]])[1]',
        '(//android.widget.LinearLayout[@clickable="true"][.//android.widget.TextView[starts-with(@text,"#")]])[1]',
        '(//android.widget.TextView[@clickable="true"][starts-with(@text,"#")])[1]',
        '(//androidx.recyclerview.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[1]',
        '(//androidx.recyclerview.widget.RecyclerView/android.widget.LinearLayout[@clickable="true"])[1]',
    ])
    _post_screen_xml_markers_rids: List[str] = field(default_factory=lambda: [
        ":id/g19",
        ":id/qrb",
    ])
    _post_screen_xml_markers_en: List[str] = field(default_factory=lambda: [
        "add a description",
    ])
    _post_screen_xml_markers_fr: List[str] = field(default_factory=lambda: [
        "ajouter une description",
    ])

    @property
    def caption_input(self) -> List[str]:
        return self._caption_input_en + self._caption_input_fr + self._caption_input_rids

    @property
    def post_btn(self) -> List[str]:
        return self._post_btn_rids + self._post_btn_en + self._post_btn_fr

    @property
    def post_screen_indicators(self) -> List[str]:
        return self.post_btn + self.caption_input

    @property
    def post_screen_xml_markers(self) -> List[str]:
        return (
            self._post_screen_xml_markers_rids
            + self._post_screen_xml_markers_en
            + self._post_screen_xml_markers_fr
        )

    def has_post_screen_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return any(marker.lower() in lowered_xml for marker in self.post_screen_xml_markers)

    @property
    def hashtag_suggestion_nodes(self) -> List[str]:
        return self._hashtag_suggestion_nodes

    @property
    def hashtag_suggestion_rows(self) -> List[str]:
        return self._hashtag_suggestion_rows

    @property
    def publish_confirm_dialog(self) -> List[str]:
        return self._publish_confirm_dialog_en + self._publish_confirm_dialog_fr

    @property
    def publish_confirm_btn(self) -> List[str]:
        return self._publish_confirm_btn_en + self._publish_confirm_btn_fr

    @property
    def keyboard_overlay_indicators(self) -> List[str]:
        return self._keyboard_overlay_indicators


PUBLISH_COMPOSER_SELECTORS = PublishComposerSelectors()
