"""Savoir qu'une vidéo est déjà likée — sans quoi le bot retire ses propres likes.

`video_already_liked` portait **quinze** sélecteurs et ne répondait sur **aucun** des 117 écrans
capturés. Deux raisons cumulées : `@content-desc="Video liked"` est un libellé que TikTok n'emploie
pas, et la moitié « resource-id » nommait `f4u`/`f57`, la paire de 43.1.4, alors que 46.6.3 rend
`g2c`/`g2w`. `_is_video_already_liked()` répondait donc toujours non.

Ce n'est pas une optimisation manquée. Sur TikTok, retaper « j'aime » sur une vidéo déjà likée la
**délike**. Une vérification bloquée sur « non » veut dire que le bot retire ses propres likes sur
toute vidéo croisée deux fois — et compte un like à chaque fois qu'il le fait.

Mesuré sur appareil le 2026-08-30, la même vidéo avant et après : le bouton d'invitation
(« Attribuer un « J'aime » à la vidéo. 35,6 K ») **disparaît**, et l'icône voisine passe à
`selected="true"`. L'ancre principale lit ce second fait et ne cite aucun id, donc elle survivra au
prochain renommage : zéro avant le like, exactement un après, rien sur les 117 autres écrans.

Les écrans sont des captures réelles, anonymisées, lues comme `d.xpath()` les lit
(`parse_ui_dump`) : une vidéo déjà aimée, ouverte depuis l'onglet « Vidéos aimées » du profil
propre, sur 43.1.4 (Pixel 3a) et 47.0.3 (Pixel 6a), le 2026-09-27 ; des vidéos du fil non aimées
sur 43.1.4 et 47.0.3 en français, 46.9.3 en anglais. Sur ces deux versions, le bouton d'invitation
ne disparaît pas : il devient « Vidéo aimée ». Aucun téléphone n'a TikTok en anglais : pas de vidéo
aimée anglaise.
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_STATE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _screen(name):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


def _reads_liked(tree):
    return any(tree.xpath(selector) for selector in VIDEO_STATE_SELECTORS.video_already_liked)


@pytest.mark.parametrize("name", ["tt4314_fr_liked_video.xml", "tt4703_fr_liked_video.xml"])
def test_a_liked_video_is_recognised_on_both_versions(name):
    assert _reads_liked(_screen(name))


@pytest.mark.parametrize("name", ["tt4314_fr_for_you_video.xml", "tt4703_fr_for_you_video.xml",
                                  "tt4693_en_for_you_video.xml"])
def test_an_unliked_video_is_not_called_liked(name):
    """Le versant qui compte : dire oui à tort ferait SAUTER le like ; dire non à tort le RETIRE."""
    assert not _reads_liked(_screen(name))


def test_the_first_anchor_needs_no_resource_id():
    """Ce qui a tué la liste précédente est d'avoir été écrite entièrement en ids d'une version.
    La marque `selected` est ce que l'app pose, quel que soit le nom qu'elle donne à l'icône."""
    first = VIDEO_STATE_SELECTORS.video_already_liked[0]

    assert "resource-id" not in first
    assert '@selected="true"' in first


def test_the_label_tiktok_never_writes_is_gone():
    """`@content-desc="Video liked"` n'existe sur aucun des 117 ecrans captures."""
    assert not any(
        '"Video liked"' in selector for selector in VIDEO_STATE_SELECTORS.video_already_liked
    )
