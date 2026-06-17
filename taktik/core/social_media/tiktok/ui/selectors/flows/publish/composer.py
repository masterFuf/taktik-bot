"""Selectors for composing the final TikTok publish payload."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class PublishComposerSelectors:
    """Selectors for caption entry, hashtag suggestions, and final submit."""

    _caption_input_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/g19")]',
        '//android.widget.EditText[@clickable="true"][1]',
        '(//android.widget.EditText)[1]',
    ])
    _post_btn_base: List[str] = field(default_factory=lambda: resource_ids("qrb", "post_btn"))
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
    _post_screen_xml_markers_base: List[str] = field(default_factory=lambda: [
        ":id/g19",
        ":id/qrb",
    ])

    @property
    def caption_input(self) -> List[str]:
        return self._caption_input_base + L("publish_composer.caption_input")

    @property
    def post_btn(self) -> List[str]:
        return self._post_btn_base + L("publish_composer.post_btn")

    @property
    def post_screen_indicators(self) -> List[str]:
        return self.post_btn + self.caption_input

    @property
    def post_screen_xml_markers(self) -> List[str]:
        return self._post_screen_xml_markers_base + L("publish_composer.post_screen_xml_markers")

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
        return L("publish_composer.publish_confirm_dialog")

    @property
    def publish_confirm_btn(self) -> List[str]:
        return L("publish_composer.publish_confirm_btn")

    @property
    def keyboard_overlay_indicators(self) -> List[str]:
        return self._keyboard_overlay_indicators


PUBLISH_COMPOSER_SELECTORS = PublishComposerSelectors()
