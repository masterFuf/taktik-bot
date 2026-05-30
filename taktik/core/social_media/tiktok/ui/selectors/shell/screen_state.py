"""Sélecteurs UI pour la détection d'états et debug TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class DetectionSelectors:
    """Sélecteurs pour la détection d'états et debug TikTok."""
    
    # === Détection de pages problématiques ===
    error_message: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "error")]',
        '//android.widget.TextView[contains(@text, "erreur")]',
        '//android.widget.TextView[contains(@text, "Something went wrong")]'
    ])
    
    network_error: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "network")]',
        '//android.widget.TextView[contains(@text, "réseau")]',
        '//android.widget.TextView[contains(@text, "No internet")]'
    ])
    
    # === Détection de restrictions ===
    rate_limit: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "too many")]',
        '//android.widget.TextView[contains(@text, "trop de")]',
        '//android.widget.TextView[contains(@text, "Try again later")]'
    ])


DETECTION_SELECTORS = DetectionSelectors()
