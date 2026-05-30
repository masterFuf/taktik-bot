"""Selectors for in-flight and completion states of TikTok publish."""

from dataclasses import dataclass, field
from typing import List

from ._shared import resource_ids


@dataclass
class PublishProgressSelectors:
    """Selectors for publish progress and success states."""

    _publish_progress_rids: List[str] = field(default_factory=lambda: resource_ids("x44"))
    _publish_progress_text_nodes: List[str] = field(default_factory=lambda: [
        '//*[@text and @bounds]',
    ])
    _success_en: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "successfully")]',
        '//*[contains(@text, "published")]',
        '//*[contains(@content-desc, "Posted")]',
    ])
    _success_fr: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "publi\u00e9")]',
        '//*[contains(@text, "succ\u00e8s")]',
    ])

    @property
    def publish_progress_indicator(self) -> List[str]:
        return self._publish_progress_rids

    @property
    def publish_progress_text_nodes(self) -> List[str]:
        return self._publish_progress_text_nodes

    @property
    def success_indicator(self) -> List[str]:
        return self._success_en + self._success_fr


PUBLISH_PROGRESS_SELECTORS = PublishProgressSelectors()
