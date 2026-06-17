"""Selectors for entering the TikTok publish flow."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class PublishCreationEntrySelectors:
    """Selectors for the home/create entrypoint of the publish flow."""

    _create_btn_base: List[str] = field(default_factory=lambda: resource_ids("nc_", "mkn"))
    _home_ready_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nc_")]',
        '//*[contains(@resource-id, ":id/mkn")]',
    ])

    @property
    def create_btn(self) -> List[str]:
        return self._create_btn_base + L("publish_creation_entry.create_btn")

    @property
    def home_ready_indicators(self) -> List[str]:
        return self._home_ready_indicators_base + L("publish_creation_entry.home_ready_indicators")


PUBLISH_CREATION_ENTRY_SELECTORS = PublishCreationEntrySelectors()
