"""Shared helpers for TikTok video selector catalogs."""

from typing import List

_PKG = [
    "com.zhiliaoapp.musically",
    "com.ss.android.ugc.trill",
    "com.ss.android.ugc.aweme",
]


def resource_ids(*ids: str) -> List[str]:
    """Generate resource-id selectors for known TikTok package variants."""
    return [f'//*[@resource-id="{pkg}:id/{rid}"]' for rid in ids for pkg in _PKG]


def resource_ids_with(*ids: str, xpath_filter: str) -> List[str]:
    """Append a shared XPath filter to each resource-id selector."""
    return [
        f'//*[@resource-id="{pkg}:id/{rid}"]{xpath_filter}'
        for rid in ids
        for pkg in _PKG
    ]


def resource_id_with_descendant(parent_id: str, child_id: str) -> List[str]:
    """Match a stable parent resource-id that contains a stable child node."""
    return [
        f'//*[@resource-id="{pkg}:id/{parent_id}" and .//*[@resource-id="{pkg}:id/{child_id}"]]'
        for pkg in _PKG
    ]
