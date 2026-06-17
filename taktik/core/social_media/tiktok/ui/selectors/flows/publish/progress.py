"""Selectors for in-flight and completion states of TikTok publish."""

from dataclasses import dataclass, field
from typing import List

from ...locales import L
from ._shared import resource_ids


@dataclass
class PublishProgressSelectors:
    """Selectors for publish progress and success states."""

    _publish_progress_rids: List[str] = field(default_factory=lambda: resource_ids("x44"))
    _publish_progress_text_nodes: List[str] = field(default_factory=lambda: [
        '//*[@text and @bounds]',
    ])

    @property
    def publish_progress_indicator(self) -> List[str]:
        return self._publish_progress_rids

    @property
    def publish_progress_text_nodes(self) -> List[str]:
        return self._publish_progress_text_nodes

    @property
    def success_indicator(self) -> List[str]:
        return L("publish_progress.success_indicator")


PUBLISH_PROGRESS_SELECTORS = PublishProgressSelectors()
