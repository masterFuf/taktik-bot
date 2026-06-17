"""Selectors for the video-edit stage of the TikTok publish flow."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L


@dataclass
class PublishEditorSelectors:
    """Selectors for editor screens and dismissable publish dialogs."""

    _video_edit_xml_markers: List[str] = field(default_factory=lambda: [
        'text="annuler"',
        'text="enregistrer"',
        'text="aperçu"',
        'text="importer"',
        'id/xay',
    ])
    _video_edit_cancel_btn_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/xay")]',
    ])

    @property
    def popup_cancel_buttons(self) -> List[str]:
        return L("publish_editor.popup_cancel_buttons")

    @property
    def video_edit_cancel_btn(self) -> List[str]:
        return self._video_edit_cancel_btn_base + L("publish_editor.video_edit_cancel_btn")

    def has_video_edit_screen_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return (
            self._video_edit_xml_markers[0] in lowered_xml
            and self._video_edit_xml_markers[1] in lowered_xml
            and any(marker in lowered_xml for marker in self._video_edit_xml_markers[2:])
        )


PUBLISH_EDITOR_SELECTORS = PublishEditorSelectors()
