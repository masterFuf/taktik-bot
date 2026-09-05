"""Le plan confronté à ce que le profil offre réellement.

Les cinq dés sont jetés AVANT d'avoir vu le profil. Ce module rattrape l'écart entre ce qui a été
tiré et ce qui peut atterrir. Les propriétés testées ici sont celles dont la perte ramènerait
exactement le comportement mesuré le 2026-09-05 : un follow sur cinq partait seul, profil ouvert
et refermé sans qu'on regarde quoi que ce soit.

Le piège à ne pas retomber est dans l'autre sens : le moteur a déjà corrigé un bug où un like qui
rendait 0 annulait le follow ET la story. « Aucune publication » et « le like a raté » ne sont pas
la même chose, et seul le premier justifie de retirer une intention.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from taktik.core.shared.behavior.interaction_plan import (  # noqa: E402
    InteractionPlan,
    resolve_against_availability,
)


def plan(**kwargs) -> InteractionPlan:
    base = dict(
        like_target=2, do_follow=False, do_comment=False, max_comments=1,
        do_watch_story=False, story_like_slot=-1, max_story_slides=3,
        do_story_like=False, max_story_likes=3,
    )
    base.update(kwargs)
    return InteractionPlan(**base)


# --- ce que le profil n'offre pas ----------------------------------------------------------

def test_une_story_tiree_mais_absente_est_retiree():
    resolu, retires = resolve_against_availability(
        plan(do_watch_story=True, do_story_like=True, story_like_slot=1),
        story_available=False, posts_count=12,
    )

    assert 'story' in retires
    assert resolu.do_watch_story is False
    assert resolu.do_story_like is False
    assert resolu.story_like_slot == -1


def test_un_profil_sans_publication_perd_like_et_commentaire():
    resolu, retires = resolve_against_availability(
        plan(like_target=3, do_comment=True), story_available=False, posts_count=0,
    )

    assert set(retires) >= {'like', 'comment'}
    assert resolu.like_target == 0
    assert resolu.do_comment is False
    assert resolu.max_comments == 0


def test_un_nombre_de_publications_inconnu_ne_retire_rien():
    """`None` veut dire « on ne sait pas », jamais « zéro » : on ne retire rien sur une ignorance."""
    initial = plan(like_target=2, do_comment=True, do_follow=True)
    resolu, retires = resolve_against_availability(
        initial, story_available=False, posts_count=None,
    )

    assert retires == []
    assert resolu is initial


# --- le follow seul --------------------------------------------------------------------------

def test_le_follow_tombe_quand_il_serait_le_seul_geste():
    resolu, retires = resolve_against_availability(
        plan(like_target=0, do_follow=True, do_watch_story=True),
        story_available=False, posts_count=8,
    )

    assert 'follow (seul)' in retires
    assert resolu.do_follow is False


def test_le_follow_reste_si_un_like_va_atterrir():
    resolu, retires = resolve_against_availability(
        plan(like_target=2, do_follow=True), story_available=False, posts_count=40,
    )

    assert retires == []
    assert resolu.do_follow is True


def test_le_follow_reste_si_une_story_existe():
    resolu, _ = resolve_against_availability(
        plan(like_target=0, do_follow=True, do_watch_story=True),
        story_available=True, posts_count=0,
    )

    assert resolu.do_follow is True
    assert resolu.do_watch_story is True


def test_le_follow_reste_si_un_commentaire_est_prevu():
    resolu, _ = resolve_against_availability(
        plan(like_target=0, do_follow=True, do_comment=True),
        story_available=False, posts_count=5,
    )

    assert resolu.do_follow is True


def test_un_profil_sans_rien_ne_garde_aucun_geste():
    resolu, retires = resolve_against_availability(
        plan(like_target=2, do_follow=True, do_comment=True, do_watch_story=True),
        story_available=False, posts_count=0,
    )

    assert resolu.do_follow is False
    assert resolu.like_target == 0
    assert resolu.do_comment is False
    assert resolu.do_watch_story is False
    assert set(retires) >= {'like', 'comment', 'story', 'follow (seul)'}


# --- ce qu'il ne doit PAS faire ---------------------------------------------------------------

def test_un_like_prevu_mais_qui_ratera_ne_retire_pas_le_follow():
    """Le bug déjà corrigé dans le moteur, dans l'autre sens.

    Ici le profil a des publications et un like est prévu : que le geste échoue ensuite (sélecteur
    cassé) ne regarde pas cette fonction. Elle décide sur ce qui est DISPONIBLE, jamais sur ce qui
    a réussi — sinon un sélecteur cassé annulerait de nouveau le follow et la story.
    """
    resolu, retires = resolve_against_availability(
        plan(like_target=2, do_follow=True), story_available=False, posts_count=30,
    )

    assert retires == []
    assert resolu.do_follow is True
    assert resolu.like_target == 2


def test_un_plan_deja_coherent_est_rendu_intact():
    initial = plan(like_target=2, do_follow=True, do_watch_story=True, do_story_like=True)
    resolu, retires = resolve_against_availability(
        initial, story_available=True, posts_count=20,
    )

    assert retires == []
    assert resolu is initial


def test_un_follow_absent_ne_devient_jamais_present():
    resolu, _ = resolve_against_availability(
        plan(like_target=0, do_follow=False, do_watch_story=True),
        story_available=False, posts_count=0,
    )

    assert resolu.do_follow is False


@pytest.mark.parametrize('posts', [0, -1])
def test_zero_et_negatif_valent_pareil(posts):
    resolu, _ = resolve_against_availability(
        plan(like_target=2), story_available=False, posts_count=posts,
    )

    assert resolu.like_target == 0
