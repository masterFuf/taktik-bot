"""Ouvrir le profil demandé, et aucun autre.

Ce fichier affirmait auparavant que l'ancre `tv_username` était « exactement une ligne, portant
exactement le handle demandé ». Remesuré le 2026-08-30 sur les DEUX versions, en demandant un
compte connu, c'était faux des deux côtés :

- sur 46.6.3 elle rendait **cinq** lignes — le handle demandé et quatre handles qui le
  prolongent (`…1`, `…s`, `…_fane`, `…__`) — et le clic prend la première, donc le run ouvrait
  un compte de fan à 12 abonnés au lieu de la cible, systématiquement ;
- sur 43.1.4 elle ne rendait **rien** : cette version nomme la ligne `ye2`, pas `tv_username`, et
  toute la liste retombait sur « la première ligne du résultat », choisie à l'aveugle.

Ce qui survit aux deux n'est pas un id mais la FORME DU TEXTE. TikTok enveloppe chaque handle
dans des isolants directionnels — `U+200E U+2068 <handle> U+2069` — à l'identique sur les deux
versions, et ces isolants **délimitent** le handle. Contenir `⁨handle⁩` veut donc dire « le handle
de cette ligne est exactement celui-là », puisque tout ce qui est plus long met un caractère là où
l'isolant fermant doit être.

Les écrans sont de vrais onglets « Utilisateurs », anonymisés : TikTok 43.1.4 (Pixel 3a, lignes
`ye2`, 9 résultats) et 46.9.3 (Pixel 6a, lignes `tv_username`, 10 résultats), en français. Les
résultats réels portaient déjà ce piège (un compte, puis des comptes dont le handle le prolonge),
mais l'anonymisation l'efface (chaque handle devient `user_N`). Les handles sont donc INVENTÉS,
posés sur les vraies lignes dans l'ordre servi (dérivé) : ils reproduisent le cas mesuré sur
46.6.3, où un compte de fan était classé AVANT le compte demandé.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS
from unit.paths import CORE

FSI, PDI, LRM = "⁨", "⁩", "‎"
FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"

#: Handles inventés, dans l'ordre des lignes servies. Cinq contiennent `demo_creator` comme
#: préfixe : un `contains` avait une chance sur cinq, et il tapait toujours la mauvaise, parce que
#: le compte de fan est classé avant le compte réel.
HANDLES = [
    "democreator", "demo_creator1", "demoo_creator", "democreatorhq", "demo_creator",
    "democreator03", "demo_creatorr", "demo_creator_fane", "demo_creator__", "demo_creator_x_fan",
]

#: Version -> (vraie capture, id de la ligne).
TABS = {
    "43.1.4": ("tt4314_fr_search_users.xml", "ye2"),
    "46.9.3": ("tt4693_fr_search_users.xml", "tv_username"),
}


def _users_tab(version, handles=HANDLES):
    """Le vrai onglet Utilisateurs de `version`, ses lignes portant `handles` dans l'ordre servi."""
    name, row_id = TABS[version]
    tree = parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))
    rows = [node for node in tree.iter() if (node.get("resource-id") or "").endswith(f":id/{row_id}")]
    assert rows and all(row.get("text", "").startswith(LRM + FSI) and row.get("text").endswith(PDI)
                        for row in rows)
    for row, handle in zip(rows, handles):
        row.set("text", f"{LRM}{FSI}{handle}{PDI}")
    return tree, [row.get("text").strip(LRM + FSI + PDI) for row in rows]


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


@pytest.mark.parametrize("version", TABS)
def test_the_row_opened_is_the_row_asked_for(version):
    """Chacun des handles de l'onglet, y compris ceux qui sont préfixes les uns des autres."""
    tree, served = _users_tab(version)
    assert len(served) >= 9
    for username in served:
        assert _tapped(tree, username) == username


@pytest.mark.parametrize("version", TABS)
def test_a_handle_absent_from_the_results_opens_nothing(version):
    """Le deuxième versant. Ne rien trouver est le bon échec : `_landed_on_profile_of` refuse
    d'INTERAGIR avec le mauvais profil, mais il ne peut pas le dé-ouvrir — ouvrir le profil d'un
    inconnu est déjà une vue sur son compte."""
    tree, _served = _users_tab(version)
    assert _tapped(tree, "quelquun_qui_nexiste_pas") is None


def test_it_works_on_the_older_version_that_renames_the_row():
    """43.1.4 nomme la ligne `ye2`. L'ancienne ancre y rendait zéro et laissait la liste retomber
    sur la première ligne, à l'aveugle."""
    tree, served = _users_tab("43.1.4")
    assert not tree.xpath('//*[contains(@resource-id, ":id/tv_username")]')
    assert _tapped(tree, "demo_creator") == "demo_creator"


@pytest.mark.parametrize("version", TABS)
def test_the_prefix_trap_is_refused(version):
    """Le cas mesuré : demander `demo_creator` quand `demo_creator1` est classé AVANT lui."""
    tree, served = _users_tab(version, handles=["demo_creator1", "demo_creator"])
    assert served[:2] == ["demo_creator1", "demo_creator"]
    assert _tapped(tree, "demo_creator") == "demo_creator"


# --- ce qui rend le tout possible ---------------------------------------------------------------


def test_the_isolates_are_what_makes_the_match_exact():
    """Sans eux, il ne reste qu'un préfixe. La marque fermante est ce qui interdit la suite."""
    selector = SEARCH_SELECTORS.user_result_selectors_for_username("creator")[0]

    assert f'"{FSI}creator{PDI}"' in selector


def test_the_tap_lands_on_the_handle_not_on_its_row():
    """La rangée fait toute la largeur et porte le bouton Suivre / Suivis : c'est le pseudo qu'on
    tape, la rangée cliquable dessous reçoit le tap (écran réel : test_tiktok_47_0_3_screens)."""
    for selector in SEARCH_SELECTORS.user_result_selectors_for_username("creator"):
        assert "ancestor::" not in selector
        assert selector.startswith("//android.widget.TextView[")


def test_no_loose_containment_survives_in_the_list():
    """La forme qui ouvrait le mauvais compte ne doit pas revenir en filet de sécurité."""
    for selector in SEARCH_SELECTORS.user_result_selectors_for_username("creator"):
        assert 'contains(@text, "creator")' not in selector
        assert "RecyclerView" not in selector
