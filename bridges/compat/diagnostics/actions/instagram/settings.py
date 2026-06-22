"""Settings actions for Instagram compat diagnostics (Cartography Lab).

Exposes the app-language change as a Lab-testable action so the Lab can
physically switch the Instagram app language on the device — instead of only
overriding the selector-overlay locale. Reuses the PRODUCTION
``ChangeLanguageWorkflow`` (no Lab-only fork), driven on the warm, already
connected Lab device facade.

After a successful switch, the Lab session's selector overlay (localized once at
session start) is stale for the new language: restart the session ("Redemarrer
session" / change device / change the forced language) to re-localize.
"""

from bridges.compat.diagnostics.actions.instagram import action


@action("settings.change_language")
def change_language(a, p):
    """Physically switch the IG app language to ``p['language']``.

    Accepts the same codes as the workflow's ``APP_LANGUAGE_NATIVE_NAMES``
    (``en`` / ``en-GB`` / ``fr-FR`` / ``fr-CA``). Returns the standard action
    result dict consumed by the Lab runner.
    """
    from taktik.core.social_media.instagram.workflows.management.language.change_language_workflow import (
        ChangeLanguageWorkflow,
    )

    language = (p.get("language") or "").strip()
    if not language:
        return {"success": False, "message": "language param is required (e.g. en, fr-FR)"}

    device_id = getattr(a.device, "device_id", None) or "lab"
    result = ChangeLanguageWorkflow(a.device, device_id).execute(language=language)
    return {
        "success": result["success"],
        "message": result.get("message", ""),
        "details": {
            "language": language,
            "native_name": result.get("native_name"),
            "error_type": result.get("error_type"),
        },
    }
