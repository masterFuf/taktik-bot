"""Small, locale-aware helpers for observable story viewer state."""

import re
from dataclasses import dataclass
from typing import Optional

from ...ui.selectors.surfaces.story_viewer import STORY_SELECTORS


_STORY_POSITION_PATTERN = re.compile(
    r"\b(?:story\s+)?(\d+)\s+(?:of|sur)\s+(\d+)\b",
    re.IGNORECASE,
)


#: Ecart de dHash (sur 64 bits) au-dela duquel deux captures ne montrent plus la meme image.
#: Le module d'empreinte le dit : deux prises du MEME visuel -- re-encodage, frame de video
#: voisine -- tiennent dans quelques bits. Douze laisse largement passer ce bruit-la.
#: Ce n'est qu'un INDICE : mesure le 2026-09-07 sur 50 stories, l'image seule ne separe pas une
#: video animee d'un changement de slide. Les preuves sont ailleurs (le libelle, le viewer parti).
SEUIL_IMAGE_DIFFERENTE = 12


def parse_story_position(value: str) -> Optional[tuple[int, int]]:
    """Extract an EN/FR ``current / total`` position from a viewer description."""
    match = _STORY_POSITION_PATTERN.search(value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


@dataclass(frozen=True)
class SlideObservation:
    """Ce qu'on peut dire de la slide affichee a un instant donne.

    `label` est une PREUVE quand il change ; `image` n'est qu'un indice. `viewer_open` a False
    est la seule chose qui tranche a elle seule dans l'autre sens : il n'y a plus de story.
    """

    viewer_open: bool
    label: Optional[str] = None
    image: Optional[str] = None


def observe_slide(device, *, with_image: bool = True) -> Optional[SlideObservation]:
    """Lire l'etat de la slide courante, ou ``None`` si l'ecran n'a pas pu etre lu. Ne leve jamais.

    Deux lectures independantes : le libelle (l'arbre) et une empreinte perceptuelle de l'ecran
    (les pixels). L'empreinte est optionnelle -- un appelant qui veut seulement savoir si le
    viewer est encore la passe ``with_image=False`` et ne paie pas la capture.

    `None` et `viewer_open=False` ne veulent surtout pas dire la meme chose : le second est une
    LECTURE (il n'y a plus de story a l'ecran), le premier une ignorance (l'appareil n'a pas
    repondu). Les confondre faisait terminer une story sur une simple erreur de lecture.
    """
    try:
        viewer_open = bool(device.xpath(STORY_SELECTORS.story_viewer_root).exists)
    except Exception:
        return None
    if not viewer_open:
        return SlideObservation(viewer_open=False)

    try:
        element = device.xpath(STORY_SELECTORS.story_viewer_text_container).get(timeout=0.5)
        if element is not None:
            attributs = getattr(element, "attrib", None) or {}
            brut = attributs.get("content-desc") or attributs.get("text") or ""
            label = " ".join(str(brut).split()) or None
    except Exception:
        label = None

    image = None
    if with_image:
        try:
            from taktik.core.shared.vision.fingerprint import dhash
            from taktik.core.shared.vision.screen_text import screenshot_pil

            image = dhash(screenshot_pil(device, timeout_seconds=4.0))
        except Exception:
            image = None

    return SlideObservation(viewer_open=True, label=label, image=image)


def compare_slides(
    before: Optional[SlideObservation],
    after: Optional[SlideObservation],
    *,
    seuil_image: int = SEUIL_IMAGE_DIFFERENTE,
) -> str:
    """Ce qui s'est passe entre deux observations, sans jamais l'inventer.

    Rend l'un de : ``'gone'`` (le viewer a disparu), ``'advanced'`` (preuve que la slide a
    change), ``'unsure'`` (l'image a change, mais rien ne prouve que ce n'est pas une video qui
    bouge), ``'same'`` (rien n'indique un changement).

    L'ordre n'est pas arbitraire : une preuve prime toujours sur un indice. Mesure du 2026-09-07,
    50 stories sur quatre appareils : le libelle rate les slides postees dans la meme heure, et
    l'image seule ne distingue pas une video animee d'une transition. Aucun des deux ne suffit ;
    'unsure' est ce qui reste quand on refuse de trancher a la place de la mesure.
    """
    if after is None:
        return 'unsure'
    if not after.viewer_open:
        return 'gone'
    if before is None:
        return 'same'

    if before.label and after.label and before.label != after.label:
        return 'advanced'

    if before.image and after.image:
        from taktik.core.shared.vision.fingerprint import hamming_distance

        ecart = hamming_distance(before.image, after.image)
        if ecart is not None and ecart >= seuil_image:
            return 'unsure'

    return 'same'
