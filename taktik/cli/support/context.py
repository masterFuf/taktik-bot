# Shared CLI translation state.
# main.py calls update_language_state() whenever the language changes.
# All prompt modules call get_translations() at function call time.

_state: dict = {
    'translations': {},
    'banner': '',
}


def get_translations() -> dict:
    """Return the currently active translations dict."""
    return _state['translations']


def get_banner() -> str:
    """Return the currently active banner string."""
    return _state['banner']


def update_language_state(translations: dict, banner: str) -> None:
    """Called by set_language() in main.py after a language change."""
    _state['translations'] = translations
    _state['banner'] = banner
