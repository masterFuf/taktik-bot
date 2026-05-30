"""Shared helpers for TikTok publish selector catalogs."""

from typing import List


def resource_ids(*ids: str) -> List[str]:
    """Generate package-agnostic resource-id selectors."""
    return [f'//*[contains(@resource-id, ":id/{rid}")]' for rid in ids]
