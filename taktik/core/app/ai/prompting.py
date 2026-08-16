"""Prompt primitives shared by the AI surfaces.

`platform_label` turns a platform key into the name a prompt should show a model. It lived
in the OpenRouter provider while both the provider and the comment generators needed it,
which is the only thing that made splitting them look circular. It is neither transport nor
comment logic, so it belongs to neither.
"""

PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok"}


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get((platform or "instagram").lower(), (platform or "Instagram").title())


__all__ = ["platform_label", "PLATFORM_LABELS"]
