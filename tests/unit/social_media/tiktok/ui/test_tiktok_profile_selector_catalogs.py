"""Le catalogue possède ce qui s'écrit à l'écran — y compris les sondes en texte brut.

Ce fichier affirmait auparavant que `verified_description_probe == "Verified"` et que
`private_text_probe == "private"`. Il verrouillait donc deux mots ANGLAIS en dur, sur un projet
dont les trois téléphones sont en français : le test restait vert pendant que `is_verified` et
`is_private` répondaient « non » pour chaque profil TikTok jamais enregistré. Un test peut très
bien garder un bug ; celui-ci le gardait.

Les deux champs sont partis avec leur dernier appelant. Ce qui reste vérifiable est le contrat :
ces deux faits se lisent maintenant par des LISTES de sélecteurs, comme tout le reste de la
surface, donc l'overlay de locale s'y applique et une ancre structurelle peut y vivre.
"""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


def test_the_website_probe_still_lives_in_the_catalog():
    """Elle, elle survit : un lien s'écrit pareil dans toutes les langues."""
    assert PROFILE_SELECTORS.website_text_probe == "http"


def test_verified_and_private_are_read_through_selector_lists():
    """Et non par un mot écrit en dur dans l'extracteur, qui ne peut pas être localisé."""
    assert isinstance(PROFILE_SELECTORS.verified_badge, list)
    assert isinstance(PROFILE_SELECTORS.private_indicator, list)


def test_the_dead_english_probes_are_gone():
    """Une garde, pas une formalité : les remettre remettrait le bug avec elles."""
    assert not hasattr(PROFILE_SELECTORS, "verified_description_probe")
    assert not hasattr(PROFILE_SELECTORS, "private_text_probe")


def test_profile_bio_button_fallback_is_catalog_owned():
    assert PROFILE_SELECTORS.bio_button_fallback_selector == {
        "className": "android.widget.Button",
        "clickable": True,
    }
