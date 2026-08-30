"""Sous quel compte une session TikTok écrit ce qu'elle fait.

Le défaut que ce fichier garde, mesuré le 2026-08-30 : `get_db_service().get_or_create_account(...)`
**a l'air** neutre et ne l'est pas — il délègue au dépôt Instagram, dont la requête est
`WHERE platform = 'instagram'`. Appelé pour un run TikTok, il rend donc la ligne INSTAGRAM qui
porte le même pseudo.

Comme `accounts.legacy_account_id` est numéroté par plateforme, l'identifiant rendu est un nombre
parfaitement valide qui appartient à un autre compte. Rien ne casse. Simplement, tout ce qui est
écrit dessous ne se joint plus à rien côté TikTok, et le lecteur voit un compte qui n'a rien fait.

Constaté dans les données : cinq DM TikTok classés sous **6590**, l'identifiant Instagram de
@marvin.ndiaye.extraits, alors que les interactions TikTok de ce compte sont sous **4982**.
L'attribution des nouveaux abonnés joint les notifications aux interactions sur `account_id` —
elle ne pouvait donc répondre que « jamais engagé », pour tout le monde et pour toujours.
"""

import ast
import io
import pathlib

import pytest

from taktik.core.database.tiktok_account_identity import looks_like_tiktok_handle

_CORE = pathlib.Path(__file__).resolve().parents[3]


# --- ce qui est un pseudo, et ce qui n'en est pas -------------------------------------------------


@pytest.mark.parametrize("handle", [
    "allocingles",
    "keo.2",
    "marvin.ndiaye.extraits",
    "youssoufdiallo3300",
    "a_b.c",
])
def test_a_real_handle_is_accepted(handle):
    assert looks_like_tiktok_handle(handle) is True


@pytest.mark.parametrize("shown", [
    "Allocin(gl)és",      # le nom d'affichage réel de @allocingles
    "Enzo Resell",        # espace
    "MarvinFan",          # majuscules : c'est ce qui l'a fait passer quand on minusculait avant
    "..........",         # pseudo tout-emoji mangé par le dump
    "",
    None,
])
def test_a_display_name_is_refused(shown):
    """Le test porte sur la valeur BRUTE. Les pseudos TikTok sont en minuscules par construction,
    donc une majuscule prouve qu'on tient un nom d'affichage — et minusculer d'abord laissait
    passer `MarvinFan`, exactement le genre de ligne qui ne se joint à rien."""
    assert looks_like_tiktok_handle(shown) is False


# --- le chemin de résolution ------------------------------------------------------------------------


def _source(relative: str) -> str:
    return io.open(_CORE / relative, encoding="utf-8").read()


def _calls(relative: str) -> set:
    """Every `a.b.c(...)` actually CALLED in a module, as dotted names.

    Read from the syntax tree rather than from the text, because the first version of this guard
    searched the source for the forbidden call and tripped on the comments that explain why it is
    forbidden. A guard that cannot tell code from prose is a guard nobody can document around.
    """
    names = set()
    for node in ast.walk(ast.parse(_source(relative))):
        if not isinstance(node, ast.Call):
            continue
        parts = []
        target = node.func
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        elif isinstance(target, ast.Call) and isinstance(target.func, ast.Name):
            parts.append(target.func.id + "()")
        if parts:
            names.add(".".join(reversed(parts)))
    return names


@pytest.mark.parametrize("module", [
    "bridges/tiktok/engagement/runtime/notifications/persistence.py",
    "bridges/tiktok/workflows/engagement/runtime/dm_persistence.py",
])
def test_no_tiktok_writer_resolves_its_account_through_instagram(module):
    """La garde qui compte. Les deux modules appelaient la façade neutre-en-apparence ; aucun ne
    doit y revenir, parce que l'erreur est invisible : elle rend un identifiant valide."""
    called = _calls(module)

    assert "get_db_service().get_or_create_account" not in called, (
        f"{module} résout son compte via le dépôt Instagram — les lignes écrites "
        "appartiendront à un autre compte et ne se joindront à rien"
    )
    assert "resolve_tiktok_account_id" in called, (
        f"{module} doit passer par resolve_tiktok_account_id"
    )


def test_the_shared_resolver_goes_to_the_tiktok_repository():
    """Écrit une fois, parce que c'était faux deux fois de la même façon."""
    called = _calls("taktik/core/database/tiktok_account_identity.py")

    assert any(name.endswith("tiktok.get_or_create_account") for name in called)
    assert "get_db_service().get_or_create_account" not in called
