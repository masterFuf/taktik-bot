"""Prompt primitives shared by the AI surfaces.

`platform_label` turns a platform key into the name a prompt should show a model. It lived
in the OpenRouter provider while both the provider and the comment generators needed it,
which is the only thing that made splitting them look circular. It is neither transport nor
comment logic, so it belongs to neither.
"""

PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok"}


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get((platform or "instagram").lower(), (platform or "Instagram").title())


def cacheable_system(stable: str, variable: str = "") -> list:
    """Build a system message split into a CACHED prefix and a per-call remainder.

    Gemini bills a cache hit at a tenth of the normal input price
    ($0.025 vs $0.25 per M on the analysis model), but the discount is NOT automatic:
    measured against production prompts, implicit caching never fired once — every call
    paid full price for a prefix that was byte-identical each time. An explicit
    `cache_control` breakpoint is what activates it.

    `stable` must be identical across calls (taxonomy + generic instructions); anything
    that varies per account, per language or per profile belongs in `variable`, AFTER the
    breakpoint, or every call writes a fresh cache entry instead of reading one.

    A prefix shorter than roughly 1.5k tokens is silently not cached by the provider (the
    standalone bot, which gets no injected taxonomy, lands there) — harmless, just no gain.
    """
    blocks = [{"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}}]
    if variable:
        blocks.append({"type": "text", "text": variable})
    return blocks

__all__ = ["platform_label", "PLATFORM_LABELS", "cacheable_system"]
