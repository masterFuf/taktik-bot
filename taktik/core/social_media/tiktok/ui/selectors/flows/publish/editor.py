"""Selectors for the video-edit stage of the TikTok publish flow."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PublishEditorSelectors:
    """Selectors for editor screens and dismissable publish dialogs."""

    _popup_cancel_buttons: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="CANCEL"]',
        '//android.widget.Button[contains(@text, "Cancel")]',
        '//android.widget.Button[contains(@text, "Annuler")]',
        '//android.widget.Button[contains(@text, "Not now")]',
        '//android.widget.Button[contains(@text, "Non merci")]',
    ])
    _video_edit_xml_markers: List[str] = field(default_factory=lambda: [
        'text="annuler"',
        'text="enregistrer"',
        'text="aper\u00e7u"',
        'text="importer"',
        'id/xay',
    ])
    _video_edit_cancel_btn: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xay")]',
        '//android.widget.Button[@text="Annuler"]',
        '//android.widget.TextView[@text="Annuler"]',
        '//android.widget.Button[contains(@text, "Cancel")]',
    ])

    @property
    def popup_cancel_buttons(self) -> List[str]:
        return self._popup_cancel_buttons

    @property
    def video_edit_cancel_btn(self) -> List[str]:
        return self._video_edit_cancel_btn

    def has_video_edit_screen_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return (
            self._video_edit_xml_markers[0] in lowered_xml
            and self._video_edit_xml_markers[1] in lowered_xml
            and any(marker in lowered_xml for marker in self._video_edit_xml_markers[2:])
        )


PUBLISH_EDITOR_SELECTORS = PublishEditorSelectors()
