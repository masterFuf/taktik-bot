"""Ouvrir le profil demandé, et aucun autre.

Ce fichier affirmait auparavant que l'ancre `tv_username` était « exactement une ligne, portant
exactement le handle demandé ». Remesuré le 2026-08-30 sur les DEUX versions, en demandant
`@lena_situations`, c'était faux des deux côtés :

- sur 46.6.3 elle rendait **cinq** lignes — `lena_situations1`, `lena_situations`,
  `lena_situationss`, `lena_situations_fane`, `lena_situations__` — et le clic prend la première,
  donc le run ouvrait un compte de fan à 12 abonnés au lieu de la cible, systématiquement ;
- sur 43.1.4 elle ne rendait **rien** : cette version nomme la ligne `ye2`, pas `tv_username`, et
  toute la liste retombait sur « la première ligne du résultat », choisie à l'aveugle.

Ce qui survit aux deux n'est pas un id mais la FORME DU TEXTE. TikTok enveloppe chaque handle
dans des isolants directionnels — `U+200E U+2068 <handle> U+2069` — à l'identique sur les deux
versions, et ces isolants **délimitent** le handle. Contenir `⁨handle⁩` veut donc dire « le handle
de cette ligne est exactement celui-là », puisque tout ce qui est plus long met un caractère là où
l'isolant fermant doit être.

Les fixtures reproduisent les vraies lignes capturées, avec leurs vrais voisins trompeurs.
"""

import pytest
from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

FSI, PDI, LRM = "⁨", "⁩", "‎"

#: Les dix lignes réellement servies pour la requête « lena_situations » (46.6.3, 2026-08-30).
#: Cinq d'entre elles contiennent le handle demandé comme préfixe : le `contains` avait une
#: chance sur cinq, et il tapait toujours la mauvaise, parce que TikTok classe le fan account
#: avant le compte réel.
ROWS = [
    "lenasituations", "lena_situations1", "lenaa_situations", "lenasituationshq",
    "lena_situations", "lenasituations03", "lena_situationss", "lena_situations_fane",
    "lena_situations__", "lena_situations_x_fan",
]


def _users_tab(rows=ROWS, resource_id="tv_username"):
    """L'onglet Utilisateurs, dans la forme que le téléphone envoie (balises renommées par u2)."""
    cells = "".join(
        '<android.view.ViewGroup clickable="true">'
        f'<android.widget.TextView resource-id="com.zhiliaoapp.musically:id/{resource_id}"'
        f' text="{LRM}{FSI}{handle}{PDI}"/>'
        '</android.view.ViewGroup>'
        for handle in rows
    )
    return etree.fromstring(f"<hierarchy>{cells}</hierarchy>".encode("utf-8"))


def _tapped(tree, username):
    """Ce que `_find_and_click` taperait : première liste qui matche, premier noeud de celle-ci."""
    for selector in SEARCH_SELECTORS.user_result_selectors_for_username(username):
        found = tree.xpath(selector)
        if found:
            for node in found[0].iter():
                text = node.get("text") or ""
                if text.startswith(LRM + FSI):
                    return text.strip(LRM + FSI + PDI)
    return None


# --- la question qui compte -------------------------------------------------------------------


@pytest.mark.parametrize("username", ROWS)
def test_the_row_opened_is_the_row_asked_for(username):
    """Chacun des dix handles, y compris ceux qui sont préfixes les uns des autres."""
    assert _tapped(_users_tab(), username) == username


def test_a_handle_absent_from_the_results_opens_nothing():
    """Le deuxième versant. Ne rien trouver est le bon échec : `_landed_on_profile_of` refuse
    d'INTERAGIR avec le mauvais profil, mais il ne peut pas le dé-ouvrir — ouvrir le profil d'un
    inconnu est déjà une vue sur son compte."""
    assert _tapped(_users_tab(), "quelquun_qui_nexiste_pas") is None


def test_it_works_on_the_older_version_that_renames_the_row():
    """43.1.4 nomme la ligne `ye2`. L'ancienne ancre y rendait zéro et laissait la liste retomber
    sur la première ligne, à l'aveugle."""
    assert _tapped(_users_tab(resource_id="ye2"), "lena_situations") == "lena_situations"


def test_the_prefix_trap_is_refused():
    """Le cas mesuré : demander `lena_situations` quand `lena_situations1` est classé AVANT lui."""
    tree = _users_tab(rows=["lena_situations1", "lena_situations"])
    assert _tapped(tree, "lena_situations") == "lena_situations"


# --- ce qui rend le tout possible ---------------------------------------------------------------


def test_the_isolates_are_what_makes_the_match_exact():
    """Sans eux, il ne reste qu'un préfixe. La marque fermante est ce qui interdit la suite."""
    selector = SEARCH_SELECTORS.user_result_selectors_for_username("creator")[0]

    assert f'"{FSI}creator{PDI}"' in selector
    assert 'ancestor::*[@clickable="true"][1]' in selector


def test_no_loose_containment_survives_in_the_list():
    """La forme qui ouvrait le mauvais compte ne doit pas revenir en filet de sécurité."""
    for selector in SEARCH_SELECTORS.user_result_selectors_for_username("creator"):
        assert 'contains(@text, "creator")' not in selector
        assert "RecyclerView" not in selector
