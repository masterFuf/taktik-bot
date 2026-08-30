"""Publier un post texte, et refuser de publier du vide.

Le format TEXTE de TikTok est le contenu le moins cher qui soit : rien à filmer, rien à monter,
rien à téléverser. Le trajet est court — Créer, TEXTE, écrire, Terminé, choisir la destination —
et c'est justement pour ça que ce fichier verrouille surtout les **refus**.

Deux d'entre eux viennent d'une erreur réelle. La saisie passe par le clavier TAKTIK parce que
`set_text` n'existe pas sur ces appareils (`NoSuchMethodException` sur `InputManager.getInstance`),
et ce clavier veut un **numéro de série**, pas un objet device. Lui passer le mauvais argument le
fait échouer en silence et rendre False : le composeur garde son texte d'invite, et l'écran donne
l'impression d'avoir refusé le texte. J'ai perdu une heure là-dessus et j'ai même documenté le flux
comme bloqué avant de comprendre. D'où la relecture du composeur avant toute validation : un
placeholder n'est pas du texte, et publier là-dessus mettrait un post vide sur le compte.
"""

import pytest

from taktik.core.social_media.tiktok.services.publish.text_post import (
    _looks_written,
    publish_text_post,
)


class _Screen:
    """Un écran qui accepte les taps qu'on lui autorise et rend le texte qu'on lui donne."""

    def __init__(self, *, composer_text="", refuse=(), no_published_indicator=False):
        self.composer_text = composer_text
        self.refuse = set(refuse)
        self.no_published_indicator = no_published_indicator
        self.tapped = []

    def tap(self, selectors, timeout=4):
        label = _label_of(selectors)
        self.tapped.append(label)
        return label not in self.refuse

    def xpath(self, selector):
        screen = self

        class _Node:
            @property
            def exists(self):
                if "lien" in selector.lower() or "link" in selector.lower():
                    return not screen.no_published_indicator
                return "hnq" in selector or "EditText" in selector

            @property
            def text(self):
                return screen.composer_text

            def click(self):
                pass

            def all(self):
                return [self] if self.exists else []

            def get_text(self):
                return screen.composer_text

        return _Node()


def _label_of(selectors) -> str:
    joined = " ".join(selectors or ())
    for needle, label in (
        ("TEXTE", "mode"), ("TEXT", "mode"),
        ("Terminé", "done"), ("Done", "done"),
        ("fil", "feed"), ("feed", "feed"),
        ("Story", "story"),
        ("hnq", "field"), ("EditText", "field"),
    ):
        if needle in joined:
            return label
    return "create"


def _publish(screen, text, *, typed=True, **kwargs):
    """Publie sur le double, sans dormir.

    Les attentes du service sont reelles — le composeur met quatre secondes a s'ouvrir — et n'ont
    rien a faire dans une suite unitaire : sans ce remplacement ce fichier prend 84 secondes.
    """
    import taktik.core.social_media.tiktok.services.publish.text_post as module

    original_type = module.type_text_human
    original_sleep = module.time.sleep
    original_timeout = module._PUBLISH_TIMEOUT
    module.type_text_human = lambda serial, body: typed
    module.time.sleep = lambda _seconds: None
    # Le delai de publication est reel lui aussi : sans plafond, le cas « rien ne confirme »
    # tournerait vingt-cinq secondes a vide.
    module._PUBLISH_TIMEOUT = 0.01
    try:
        return publish_text_post(screen, "SERIAL", text, click=screen.tap, **kwargs)
    finally:
        module.type_text_human = original_type
        module.time.sleep = original_sleep
        module._PUBLISH_TIMEOUT = original_timeout


# --- ce qu'on refuse de publier ------------------------------------------------------------------


def test_an_empty_text_is_refused_before_anything_is_tapped():
    screen = _Screen()

    result = _publish(screen, "   ")

    assert result["success"] is False
    assert result["error"] == "empty text"
    assert screen.tapped == []


def test_a_composer_still_showing_its_placeholder_is_not_published():
    """Le refus qui compte. Quand la saisie échoue, le champ garde « Saisis quelque chose… » —
    ce n'est pas du texte, et valider là-dessus met un post vide en ligne."""
    screen = _Screen(composer_text="Saisis quelque chose…")

    result = _publish(screen, "Mon vrai texte")

    assert result["success"] is False
    assert "rather than the text" in result["error"]
    assert "done" not in screen.tapped


def test_a_keyboard_that_did_not_type_stops_the_run():
    screen = _Screen(composer_text="Saisis quelque chose…")

    result = _publish(screen, "Mon texte", typed=False)

    assert result["success"] is False
    assert result["error"] == "the keyboard did not type"


def test_a_missing_text_mode_says_so_rather_than_publishing_something_else():
    """La création s'ouvre sur CRÉER. Sans l'onglet TEXTE on est sur la caméra, et continuer
    reviendrait à publier autre chose que ce qui a été demandé."""
    screen = _Screen(refuse={"mode"})

    result = _publish(screen, "Mon texte")

    assert result["success"] is False
    assert result["step"] == "mode_text"


# --- ce qui prouve la publication ------------------------------------------------------------------


def test_the_tap_on_the_destination_is_not_the_proof():
    """TikTok lève sa feuille de partage dès qu'un post part. Sans elle, rien ne dit que le post
    est en ligne — et sur une surface de publication, croire le tap fait annoncer des posts qui
    n'existent pas.

    Le composeur répond normalement ici : seul l'indicateur de publication manque, pour que
    l'échec porte sur la vérification et non sur une étape d'avant.
    """
    screen = _Screen(composer_text="Mon texte", no_published_indicator=True)

    result = _publish(screen, "Mon texte")

    assert result["success"] is False
    assert result["step"] == "verify"


def test_a_published_post_reports_where_it_went():
    screen = _Screen(composer_text="Mon texte")

    result = _publish(screen, "Mon texte")

    assert result["success"] is True
    assert result["step"] == "published"
    assert result["destination"] == "feed"


def test_the_story_destination_is_a_different_tap():
    screen = _Screen(composer_text="Mon texte")

    result = _publish(screen, "Mon texte", to_story=True)

    assert result["destination"] == "story"
    assert "story" in screen.tapped


# --- la relecture du composeur ----------------------------------------------------------------------


@pytest.mark.parametrize("written,wanted,expected", [
    ("Essai Taktik", "Essai Taktik", True),
    ("Saisis quelque chose…", "Essai Taktik", False),
    ("Say something…", "Essai Taktik", False),
    # Le nœud tronque les textes longs : exiger l'égalité refuserait un post parfaitement valide.
    ("Un texte assez long qui a ete tro", "Un texte assez long qui a ete tronque par le noeud", True),
    ("", "Essai", False),
    ("Essai", "", False),
])
def test_the_composer_is_read_back_loosely_but_not_blindly(written, wanted, expected):
    assert _looks_written(written, wanted) is expected
