"""Sélecteurs UI pour la détection d'états et debug TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'états et debug TikTok."""

    # === Détection de pages problématiques ===
    @property
    def error_message(self) -> List[str]:
        return L("detection.error_message")

    @property
    def network_error(self) -> List[str]:
        return L("detection.network_error")

    # === Détection de restrictions ===
    @property
    def rate_limit(self) -> List[str]:
        return L("detection.rate_limit")


DETECTION_SELECTORS = DetectionSelectors()
