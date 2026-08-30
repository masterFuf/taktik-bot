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


def test_a_post_without_a_caption_still_has_a_key_when_the_date_is_there():
    key = tiktok_post_key("Kéo", "· 06-12", "")

    assert key and key.endswith("nocaption")


def test_without_a_date_AND_without_a_caption_there_is_no_key():
    """Le second défaut révélé par la FYP : `tv_post_time` n'y existe pas. Une vidéo sans légende
    y serait identifiée par son seul auteur — et TOUTES les vidéos sans légende de cet auteur
    tomberaient dans la même ligne. Même arbitrage que pour l'auteur manquant : ne rien stocker."""
    assert tiktok_post_key("charli d’amelio", "", "") is None
    assert tiktok_post_key("charli d’amelio", None, None) is None


# --- deux posts différents donnent deux clés ----------------------------------------------------


def test_another_date_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Kéo", "· 06-13", CAPTION)


def test_another_caption_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Kéo", "· 06-12", "Autre chose")


def test_another_author_is_another_post():
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Marvin", "· 06-12", CAPTION)


def test_the_author_is_folded_as_hard_as_the_caption():
    """Le compromis assumé, mesuré sur la FYP le 2026-08-30.

    La première version gardait la ponctuation de l'auteur, pour que `keo.2` et `keo2` restent
    deux comptes. L'écran a tranché autrement : la FYP rend un **nom d'affichage**, pas un pseudo
    — le Lab a renvoyé `charli d'amelio`, espace et apostrophe courbe comprises — et un nom
    d'affichage porte très souvent un emoji, que le dump réduit à deux points. Garder la
    ponctuation faisait donc deux clés pour un même post, ce que la clé existe pour empêcher.

    Le prix : deux comptes dont les noms se replient pareil ne sont plus distingués par l'auteur
    seul. Il reste la date et la légende, et il faudrait que les deux publient la même légende le
    même jour pour entrer en collision. On échange un risque quotidien contre un risque rarissime.
    """
    assert tiktok_post_key("keo.2", "· 06-12", CAPTION) == tiktok_post_key("keo2", "· 06-12", CAPTION)


def test_an_emoji_in_the_display_name_keys_the_same_eaten_or_not():
    """Le vrai défaut que la FYP a révélé : l'emoji était replié dans la légende, pas dans
    l'auteur. Une créatrice dont le pseudo porte un emoji prenait deux clés selon la lecture."""
    assert tiktok_post_key("Lea 🔥", "· 06-12", CAPTION) == tiktok_post_key("Lea ..", "· 06-12", CAPTION)


def test_the_display_name_of_the_fyp_keys_cleanly():
    """Ce que le Lab a réellement renvoyé, avant correction : `tiktok:charli d'amelio:...`."""
    key = tiktok_post_key("charli d’amelio", "", "dc @Kittrell")

    assert key == "tiktok:charlidamelio:nodate:" + key.rsplit(":", 1)[-1]
    assert " " not in key and "’" not in key


# --- ce qu'on refuse d'identifier ----------------------------------------------------------------


@pytest.mark.parametrize("author", ["", "   ", "@", None])
def test_without_an_author_there_is_no_key(author):
    """Une clé sans auteur entrerait en collision entre comptes — ne rien stocker vaut mieux."""
    assert tiktok_post_key(author, "· 06-12", CAPTION) is None


def test_the_key_names_its_platform():
    """Elle cohabite avec des clés Instagram dans la même colonne, et une clé qui ne dit pas d'où
    elle vient est une clé qu'on relit mal."""
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION).startswith("tiktok:")

# --- les dates relatives ---------------------------------------------------------------------


def test_a_relative_date_does_not_make_the_key_move():
    """Le défaut mesuré le 2026-08-30, en collectant les vidéos d'un profil.

    TikTok écrit une date RELATIVE pour tout ce qui date de quelques jours — `· Il y a 20 h`,
    `· Il y a 1 j` — et bascule sur `· 06-12` ensuite. Keyée dessus, la même vidéo devient
    `ilya1j` demain et `ilya2j` après-demain : une ligne de plus par jour, et « a-t-on déjà engagé
    ce post ? » répondant non pour toujours. C'est exactement ce que la clé existe pour empêcher.
    """
    assert tiktok_post_key("Kéo", "· Il y a 20 h", CAPTION) == tiktok_post_key("Kéo", "· Il y a 1 j", CAPTION)
    assert tiktok_post_key("Kéo", "3d", CAPTION) == tiktok_post_key("Kéo", "· Il y a 1 j", CAPTION)


def test_an_absolute_date_still_separates_two_posts():
    """Une date absolue est un fait sur le post : elle reste dans la clé et continue de trier."""
    assert tiktok_post_key("Kéo", "· 06-12", CAPTION) != tiktok_post_key("Kéo", "· 06-13", CAPTION)


def test_a_recent_post_and_an_old_one_are_never_confondus():
    assert tiktok_post_key("Kéo", "· Il y a 1 j", CAPTION) != tiktok_post_key("Kéo", "· 06-12", CAPTION)


def test_the_collision_this_accepts_is_written_down():
    """Le prix, assumé : deux posts du MÊME auteur, MÊME légende, tous deux récents, partagent une
    clé. C'est le moins grave des deux échecs — une ligne dupliquée fait réengager le même post
    tous les jours, une collision en fait sauter un — et rien à l'écran ne les sépare de toute
    façon : le compte de test qui a révélé ça avait publié trois fois la même légende."""
    assert tiktok_post_key("Kéo", "· Il y a 20 h", CAPTION) == tiktok_post_key("Kéo", "· Il y a 2 j", CAPTION)

