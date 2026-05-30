"""Selectors for media picking inside the TikTok publish flow."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids


@dataclass
class PublishMediaPickerSelectors:
    """Selectors for camera/gallery entry and next-step picking."""

    _upload_btn_rids: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/ymg") and @clickable="true"]',
        '//*[contains(@resource-id, ":id/ce9") and @clickable="true"]',
        '//*[contains(@resource-id, ":id/cl2") and @clickable="true"]',
        *resource_ids("ymg", "ce9", "cl2"),
    ])
    _upload_btn_en: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Upload"]',
        '//*[contains(@content-desc, "Upload")]',
        '//*[@text="Upload"]',
        '//*[contains(@text, "Upload")]',
        '//*[contains(@text, "Gallery")]',
    ])
    _upload_btn_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Importer")]',
        '//*[contains(@text, "Galerie")]',
    ])
    _upload_dump_resource_ids: List[str] = field(default_factory=lambda: [
        "ymg",
        "ce9",
        "cl2",
    ])
    _gallery_first_item_rids: List[str] = field(default_factory=lambda: [
        '(//android.widget.ImageView[contains(@resource-id, ":id/mub")])[1]',
        '(//android.widget.GridView[contains(@resource-id, ":id/i8o")]//android.widget.ImageView)[1]',
        '(//android.widget.ImageView[contains(@resource-id, ":id/nm8")])[1]',
        '(//android.widget.GridView[contains(@resource-id, ":id/ir_")]//android.widget.ImageView)[1]',
        '//*[contains(@resource-id, ":id/ir_")]//*[@class="android.widget.ImageView"][1]',
    ])
    _gallery_picker_xml_markers: List[str] = field(default_factory=lambda: [
        ":id/i8o",
        ":id/ir_",
        ":id/mub",
        ":id/nm8",
    ])
    _camera_creation_copy_markers: List[str] = field(default_factory=lambda: [
        "ajouter un son",
        "add sound",
        'text="photo"',
        'text="texte"',
        'text="publier"',
        'text="cr\u00e9er"',
        'text="create"',
    ])
    _camera_creation_control_markers: List[str] = field(default_factory=lambda: [
        ":id/ce9",
        ":id/r3r",
        ":id/d8a",
        ":id/v5w",
    ])
    _next_btn_rids: List[str] = field(default_factory=lambda: resource_ids("uyb", "ooo", "w51", "next_btn"))
    _next_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Next"]',
        '//android.widget.Button[contains(@text, "Next")]',
        '//android.widget.TextView[contains(@text, "Next")]',
    ])
    _next_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Suivant")]',
        '//android.widget.TextView[contains(@text, "Suivant")]',
    ])

    @property
    def upload_btn(self) -> List[str]:
        return self._upload_btn_rids + self._upload_btn_en + self._upload_btn_fr

    @property
    def upload_dump_resource_ids(self) -> List[str]:
        return self._upload_dump_resource_ids

    @property
    def upload_dump_selectors(self) -> List[tuple[str, str]]:
        return [
            (rid, f'//*[contains(@resource-id, ":id/{rid}")]')
            for rid in self._upload_dump_resource_ids
        ]

    @property
    def gallery_first_item(self) -> List[str]:
        return self._gallery_first_item_rids

    def has_gallery_picker_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        return any(marker.lower() in lowered_xml for marker in self._gallery_picker_xml_markers)

    def has_camera_creation_marker(self, xml: str) -> bool:
        lowered_xml = xml.lower()
        has_camera_copy = any(marker.lower() in lowered_xml for marker in self._camera_creation_copy_markers)
        has_camera_controls = any(marker.lower() in lowered_xml for marker in self._camera_creation_control_markers)
        return has_camera_copy and has_camera_controls

    @property
    def next_btn(self) -> List[str]:
        return self._next_btn_rids + self._next_btn_en + self._next_btn_fr


PUBLISH_MEDIA_PICKER_SELECTORS = PublishMediaPickerSelectors()
