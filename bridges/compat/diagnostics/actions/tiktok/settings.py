"""App-language ACTION for TikTok compat diagnostics.

In the Lab because the language switch is the prerequisite of every English measurement: all
three phones are fr-FR, so until this existed, every English catalogue entry was a guess. Being
able to flip the app from the Lab is what makes an English auto-test run possible at all.

ACTS: it changes what the phone's TikTok speaks. It is idempotent — asking for the language
already in use costs nothing and touches no screen.
"""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.settings.change_language")
def change_language(a, p):
    """Switch the app language, and prove it switched.

    Params: target (required) — 'fr', 'en', 'en-US', 'fr-CA'...

    The result reports the language BEFORE and AFTER, because "changed" and "was already there"
    are different facts and a caller that only sees success cannot tell them apart.
    """
    target = ((p or {}).get("target") or (p or {}).get("language") or "").strip()
    if not target:
        return {"success": False, "message": "target is required (e.g. 'fr', 'en')"}

    from taktik.core.social_media.tiktok.workflows.management.language import (
        TikTokChangeLanguageWorkflow,
    )

    device = getattr(a, "device", None)
    raw = getattr(device, "_device", None) or device
    result = TikTokChangeLanguageWorkflow(raw, getattr(a, "device_id", "")).run(target)

    logger.info(
        f"tt.settings.change_language: {result.get('language_before')} -> "
        f"{result.get('language_after')} (success={result.get('success')})"
    )
    return {
        # Verified by DETECTING the language afterwards, never by the tap on the confirm button.
        "success": bool(result.get("success")),
        "message": (result.get("error")
                    or ("already set" if result.get("already_set")
                        else f"{result.get('language_before')} -> {result.get('language_after')}")),
        "details": result,
    }
