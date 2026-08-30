"""Identifier un post TikTok quand son lien ne le peut pas.

Mesuré sur appareil le 2026-08-30 : copier le lien d'une même vidéo quatre fois de suite rend
quatre URLs différentes — `vm.tiktok.com/ZN8FUVpSM`, `ZN8FUWHSs`, `ZN8FUcEWh`, `ZN8FUtvAr` — et
aucun identifiant numérique n'apparaît nulle part dans l'arbre d'accessibilité. Le lien navigue
très bien ; il est seulement inutilisable comme identité. Clé sur lui, une vidéo serait stockée une
fois par visite et « a-t-on déjà engagé ce post ? » répondrait non pour toujours.

L'identité est donc bâtie sur ce que l'écran montre ET qui ne bouge pas d'une visite à l'autre :
auteur, date de publication, empreinte de la légende. Les trois ont été mesurés sur l'écran vidéo.

Le piège que ces tests gardent surtout : **la même légende relue ne revient pas identique**. Le
dump XML transforme chaque emoji en deux points, et une apostrophe courbe ou une espace finale
suffisent à changer un hachage brut. Sans repli, le même post prendrait deux clés — et on serait
revenu au problème qu'on essaie de résoudre.
"""

import pytest

from taktik.core.database.tiktok_post_identity import tiktok_post_key


CAPTION = "Le secret de ma réussite en bio"


# --- le même post donne la même clé ------------------------------------------------------------


def test_the_same_post_read_twice_keys_the_same():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) == tiktok_post_key("Kéo", "· 06-12", CAPTION)


@pytest.mark.parametrize("author,label,caption", [
    ("  Kéo  ", "·  06-12 ", CAPTION + "  "),     # espaces de rendu
    ("@Kéo", "06-12", CAPTION),                   # arobase et ponctuation de date
    ("KÉO", "· 06-12", CAPTION.upper()),          # casse
    ("Keo", "· 06-12", "Le secret de ma reussite en bio"),  # accents repliés
])
def test_the_folds_that_a_second_read_needs(author, label, caption):
    assert tiktok_post_key(author, label, caption) == tiktok_post_key("Kéo", "· 06-12", CAPTION)


def test_an_emoji_eaten_by_the_dump_keys_like_the_emoji_itself():
    """Le piège central : AOSP remplace chaque emoji par deux points. La même légende lue avant et
    après ce massacre doit tomber sur la même clé, sinon le post est stocké deux fois."""
    intact = tiktok_post_key("Kéo", "· 06-12", "Trop fort 🔥")
    mangled = tiktok_post_key("Kéo", "· 06-12", "Trop fort ..")

    assert intact == mangled


def test_a_post_without_a_caption_still_has_a_key():
    key = tiktok_post_key("Kéo", "· 06-12", "")

    assert key and key.endswith("nocaption")


# --- deux posts différents donnent deux clés ----------------------------------------------------


def test_another_date_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Kéo", "· 06-13", CAPTION)


def test_another_caption_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Kéo", "· 06-12", "Autre chose")


def test_another_author_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Marvin", "· 06-12", CAPTION)


def test_two_close_handles_do_not_collide():
    """Les pseudos TikTok portent des points et des tirets bas. Les replier comme la légende —
    en supprimant la ponctuation — ferait entrer `keo.2` et `keo2` dans le même post."""
    assert tiktok_post_key("keo.2", "· 06-12", CAPTION) != tiktok_post_key("keo2", "· 06-12", CAPTION)


# --- ce qu'on refuse d'identifier ----------------------------------------------------------------


@pytest.mark.parametrize("author", ["", "   ", "@", None])
def test_without_an_author_there_is_no_key(author):
    """Une clé sans auteur entrerait en collision entre comptes — ne rien stocker vaut mieux."""
    assert tiktok_post_key(author, "· 06-12", CAPTION) is None


def test_the_key_names_its_platform():
    """Elle cohabite avec des clés Instagram dans la même colonne, et une clé qui ne dit pas d'où
    elle vient est une clé qu'on relit mal."""
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION).startswith("tiktok:")
