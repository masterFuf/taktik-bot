"""Changer la langue de l'application — et le prouver.

Chemin parcouru et mesuré sur appareil le 2026-08-29, dans les DEUX sens : relevé sur un téléphone
dont TikTok était en anglais, puis utilisé pour le repasser en français. Un aller simple ne prouve
rien ici : ce qu'on veut savoir, c'est que le chemin tient depuis une langue où l'on n'a pas
commencé.

Ce workflow n'est pas un confort. Les trois téléphones sont en `fr-FR`, donc chaque entrée anglaise
du catalogue était une supposition — l'audit le dit. Pouvoir basculer l'app est ce qui transforme
« probablement » en « mesuré », pour tout le catalogue.
"""

from taktik.core.social_media.tiktok.ui.selectors.flows.settings import (
    APP_LANGUAGE_NATIVE_NAMES,
    SETTINGS_SELECTORS,
)
from taktik.core.social_media.tiktok.workflows.management.language import (
    TikTokChangeLanguageWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.language.change_language_workflow import (
    _base_language,
)


class _SilentLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def _workflow(**patched) -> TikTokChangeLanguageWorkflow:
    workflow = TikTokChangeLanguageWorkflow.__new__(TikTokChangeLanguageWorkflow)
    workflow.device = None
    workflow.device_id = "test"
    workflow._notify_cb = None
    workflow.logger = _SilentLogger()
    workflow.settings = SETTINGS_SELECTORS
    for name, value in patched.items():
        setattr(workflow, name, value)
    return workflow


# --- ce qui rend le chemin possible ----------------------------------------------------------


def test_the_picker_is_addressed_by_the_native_name():
    """Le seul pas qui doit survivre à une langue inconnue est celui qui le fait : le sélecteur
    liste chaque langue dans SA propre graphie, identique quelle que soit l'UI."""
    assert APP_LANGUAGE_NATIVE_NAMES["fr"] == "Français"
    assert APP_LANGUAGE_NATIVE_NAMES["en"] == "English (UK)"
    assert APP_LANGUAGE_NATIVE_NAMES["en-US"] == "English (US)"


def test_the_language_row_climbs_to_what_is_tappable():
    """Le libellé n'est pas cliquable ; la ligne est son plus proche ancêtre cliquable — la même
    remontée que la grille de posts et les résultats de recherche."""
    selectors = SETTINGS_SELECTORS.language_row_for_native_name("Français")
    assert 'ancestor::*[@clickable="true"][1]' in selectors[0]
    assert '@text="Français"' in selectors[0]


def test_a_quote_in_a_language_name_cannot_break_the_expression():
    for selector in SETTINGS_SELECTORS.language_row_for_native_name('Ex"otic'):
        assert selector.count('"') % 2 == 0


def test_the_app_language_row_is_not_the_language_row():
    """L'écran Langue porte AUSSI une section Traductions dont les lignes affichent des noms de
    langue. Taper la mauvaise change ce qui est traduit, pas ce que l'app parle."""
    assert SETTINGS_SELECTORS.language_row != SETTINGS_SELECTORS.app_language_row


# --- ce que le workflow refuse de faire ------------------------------------------------------


def test_an_unknown_language_is_refused_before_the_screen_is_touched():
    """Aucune navigation ne doit démarrer pour une cible qu'on ne saurait pas sélectionner."""
    def _never(*_args, **_kwargs):
        raise AssertionError("le workflow a touché l'appareil pour une langue inconnue")

    result = _workflow(_open_settings=_never).run("klingon")
    assert result["success"] is False
    assert result["error_type"] == "unknown_language"
    assert result["step"] == "start"


def test_being_already_in_the_target_language_costs_no_device_time():
    """Rejouer quatre écrans pour re-choisir la langue en cours est du temps device pour rien —
    et c'est le cas courant quand un appelant fixe la langue par précaution au démarrage."""
    def _never(*_args, **_kwargs):
        raise AssertionError("le workflow a navigué alors qu'il était déjà dans la bonne langue")

    workflow = _workflow(_open_settings=_never)
    import taktik.core.social_media.tiktok.workflows.management.language.change_language_workflow as mod

    original = mod.detect_language
    mod.detect_language = lambda _device: "fr"
    try:
        result = workflow.run("fr")
    finally:
        mod.detect_language = original

    assert result["success"] is True
    assert result["already_set"] is True
    assert result["language_after"] == "fr"


def test_a_confirmed_tap_is_not_a_changed_language():
    """La question qui compte : l'app parle-t-elle la nouvelle langue ? Un sélecteur validé qui
    n'a rien appliqué ressemble exactement à un succès vu de l'appelant."""
    import taktik.core.social_media.tiktok.workflows.management.language.change_language_workflow as mod

    workflow = _workflow(
        _open_settings=lambda: True,
        _scroll_to=lambda *_a, **_k: True,
        _click=lambda *_a, **_k: True,
        _find=lambda *_a, **_k: object(),
    )
    original = mod.detect_language
    # La langue ne bouge pas malgre tous les clics reussis.
    mod.detect_language = lambda _device: "en"
    try:
        result = workflow.run("fr")
    finally:
        mod.detect_language = original

    assert result["success"] is False
    assert result["error_type"] == "language_not_applied"
    assert result["language_after"] == "en"


# --- codes de langue --------------------------------------------------------------------------


def test_a_regional_code_is_compared_on_its_base():
    """Le sélecteur parle en régional (« English (UK) »), la détection en base (« en »). Sans
    cette réduction, un changement réussi vers en-GB serait rapporté comme non appliqué."""
    assert _base_language("en-GB") == "en"
    assert _base_language("fr-CA") == "fr"
    assert _base_language("fr") == "fr"
    assert _base_language("") == ""
