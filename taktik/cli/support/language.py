"""The language of the CLI's texts: chosen at the interactive menu, English for a sub-command.

`current_translations` and `current_banner` start in English, so a command that does not go through
the root (`taktik-tiktok`) still has its texts. `set_language` changes them, and hands them to
`context`, where the menus read them.
"""
import click
from rich.console import Console

from taktik.cli.locales import fr, en
from taktik.cli.support.context import update_language_state

LANGUAGES = {
    'en': en,
    'fr': fr
}
DEFAULT_LANGUAGE = 'en'
current_translations = LANGUAGES[DEFAULT_LANGUAGE].TRANSLATIONS
current_banner = LANGUAGES[DEFAULT_LANGUAGE].BANNER

def set_language(lang_code):
    global current_translations, current_banner
    if lang_code in LANGUAGES:
        current_translations = LANGUAGES[lang_code].TRANSLATIONS
        current_banner = LANGUAGES[lang_code].BANNER
    else:
        current_translations = LANGUAGES[DEFAULT_LANGUAGE].TRANSLATIONS
        current_banner = LANGUAGES[DEFAULT_LANGUAGE].BANNER
    update_language_state(current_translations, current_banner)

console = Console()


def select_language():
    console.print("\n[bold blue]Language Selection / Sélection de la langue[/bold blue]")
    console.print("1. English")
    console.print("2. Français")
    
    choice = click.prompt(
        "\n[bold yellow]Choose your language / Choisissez votre langue[/bold yellow]",
        type=click.IntRange(1, 2),
        default=1,
        show_choices=False
    )
    
    if choice == 1:
        return 'en'
    else:
        return 'fr'
