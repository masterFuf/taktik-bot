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

