"""Keyboard actions for Instagram compat diagnostics."""

from bridges.compat.diagnostics.actions.instagram import action


@action("keyboard.press_enter")
def kb_enter(a, p):
    return a.kb.press_enter()


@action("keyboard.press_back")
def kb_back(a, p):
    a.device.press("back")
    return True


@action("keyboard.hide")
def kb_hide(a, p):
    return a.kb.hide_keyboard()


@action("keyboard.type_text")
def kb_type(a, p):
    text = p.get("text", "hello")
    return a.kb.type_text(text)


@action("keyboard.type_human")
def kb_type_human(a, p):
    """Type with human imperfections: occasional adjacent-key typos that self-correct,
    plus think-pauses. Focus a text field first (comment box / search / DM); watch the
    mirror — a wrong key appears then gets backspaced before continuing."""
    from taktik.core.shared.input.taktik_keyboard import type_text_human

    text = p.get("text") or "Trop beau ce shoot ! J'adore vraiment le rendu."
    device_id = a.device._device.serial
    ok = type_text_human(device_id, text, typos=True)
    return {"success": bool(ok), "message": f"frappe humaine: {text!r}"}

