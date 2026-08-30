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
"""

import pytest
from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_STATE_SELECTORS


def _rail(liked: bool, icon_id: str = "g2c", button_id: str = "g2w", lang: str = "fr"):
    """La colonne d'engagement d'une vidéo, dans la forme mesurée sur appareil."""
    invite = ("Attribuer un « J'aime » à la vidéo. 35,6 K « J'aime »" if lang == "fr"
              else "Like video. 35.6K likes")
    label = "J'aime" if lang == "fr" else "Like"
    # Une fois likée, l'invitation n'est plus rendue du tout.
    button = (f'<android.widget.Button resource-id="com.zhiliaoapp.musically:id/{button_id}"'
              f' content-desc="{invite}" clickable="true"/>') if not liked else ""
    return etree.fromstring(
        f'<hierarchy><android.widget.FrameLayout>{button}'
        f'<android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/{icon_id}"'
        f' content-desc="{label}" selected="{"true" if liked else "false"}"/>'
        f'</android.widget.FrameLayout></hierarchy>'.encode("utf-8")
    )


def _reads_liked(tree):
    return any(tree.xpath(selector) for selector in VIDEO_STATE_SELECTORS.video_already_liked)


@pytest.mark.parametrize("icon,button", [("g2c", "g2w"), ("f4u", "f57")])
@pytest.mark.parametrize("lang", ["fr", "en"])
def test_a_liked_video_is_recognised_on_both_versions(icon, button, lang):
    assert _reads_liked(_rail(liked=True, icon_id=icon, button_id=button, lang=lang))


@pytest.mark.parametrize("icon,button", [("g2c", "g2w"), ("f4u", "f57")])
@pytest.mark.parametrize("lang", ["fr", "en"])
def test_an_unliked_video_is_not_called_liked(icon, button, lang):
    """Le versant qui compte : dire oui à tort ferait SAUTER le like ; dire non à tort le RETIRE."""
    assert not _reads_liked(_rail(liked=False, icon_id=icon, button_id=button, lang=lang))


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
