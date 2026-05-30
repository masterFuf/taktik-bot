"""Selectors for entering the TikTok publish flow."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids


@dataclass
class PublishCreationEntrySelectors:
    """Selectors for the home/create entrypoint of the publish flow."""

    _create_btn_rids: List[str] = field(default_factory=lambda: resource_ids("nc_", "mkn"))
    _create_btn_en: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.FrameLayout[@content-desc="Create"]',
        '//android.widget.ImageView[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Create")]',
    ])
    _create_btn_fr: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@content-desc, "Cr\u00e9er")]',
    ])
    _home_ready_indicators: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nc_")]',
        '//*[contains(@resource-id, ":id/mkn")]',
        '//android.widget.Button[@content-desc="Create"]',
        '//android.widget.Button[contains(@content-desc, "Cr\u00e9er")]',
        '//android.widget.Button[contains(@content-desc, "Create")]',
        '//android.widget.FrameLayout[@content-desc="Create"]',
    ])

    @property
    def create_btn(self) -> List[str]:
        return self._create_btn_rids + self._create_btn_en + self._create_btn_fr

    @property
    def home_ready_indicators(self) -> List[str]:
        return self._home_ready_indicators


PUBLISH_CREATION_ENTRY_SELECTORS = PublishCreationEntrySelectors()
