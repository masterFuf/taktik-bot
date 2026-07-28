"""Session d'automatisation autour d'une passe de suggestions.

Ce que ce module resout, et pourquoi il ne suffisait pas d'ecrire les follows.

Un follow enregistre sans `session_id` existe bien dans `interactions`, mais il
n'appartient a aucune session — donc il ne remonte ni dans l'historique de sessions,
ni dans le snapshot `stats_*` que `finalize_session` agrege, ni dans ce qu'on montre
au client. « On a gagne tant d'abonnes grace au bot » se lit dans les sessions ; une
action orpheline est, de ce point de vue, invisible.

Or ce cas etait la norme partout ou il n'y a pas d'``InstagramAutomation`` :
`_get_session_id()` lit `automation.current_session_id` puis
`session_manager.session_id`, et aucun des deux n'existait pour le Lab ni pour le
bridge Notifications. Ce module ouvre donc une VRAIE session autour de la passe, et
la cloture avec son instantane de statistiques.

Il est volontairement minuscule et sans device : une passe de suggestions n'a pas
besoin du cycle de vie complet d'``InstagramAutomation``, seulement d'un debut, d'une
fin et d'un identifiant.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from loguru import logger

# Type de cible ecrit en base. La page Sessions du desktop mappe ce champ vers un
# libelle ; une valeur inconnue y tombe dans "Other", ce qui reste lisible mais pauvre.
SUGGESTION_TARGET_TYPE = "SUGGESTIONS"

log = logger.bind(module="instagram-suggestion-session")


def open_suggestion_session(account_id: Optional[int], *, source: str,
                            config: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Ouvrir la session et rendre son id, ou None si on ne peut pas.

    Sans compte resolu il n'y a pas de session possible : la creer sous l'id par
    defaut attribuerait le travail a quelqu'un d'autre, ce qui est pire que pas de
    session du tout.
    """
    if not account_id:
        log.warning("Pas de compte resolu : la passe de suggestions n'aura pas de session")
        return None
    try:
        from taktik.core.database.local.service import get_local_database

        session_id = get_local_database().create_session(
            account_id=account_id,
            session_name=f"Suggestions ({source})",
            target_type=SUGGESTION_TARGET_TYPE,
            target=source,
            config_used=config,
        )
        if session_id:
            log.info(f"Session de suggestions {session_id} ouverte (source: {source})")
        return session_id
    except Exception as exc:  # noqa: BLE001 — jamais fatal pour la passe
        log.warning(f"Impossible d'ouvrir une session de suggestions: {exc}")
        return None


def close_suggestion_session(session_id: Optional[int], *, status: str = "COMPLETED",
                             duration_seconds: Optional[int] = None,
                             error_message: Optional[str] = None) -> None:
    """Clore la session ET ecrire son instantane de statistiques.

    ``finalize_session`` — et pas ``update_session`` — parce que lui seul agrege les
    `interactions` de la session dans les colonnes `stats_*`. Sans cet appel la session
    resterait ACTIVE, sans heure de fin et avec des compteurs a zero alors que les
    follows sont bien en base : exactement le genre d'ecart qui fait douter de tout le
    reste des chiffres.
    """
    if not session_id:
        return
    try:
        from taktik.core.database.local.service import get_local_database

        get_local_database().finalize_session(
            session_id, status,
            duration_seconds=duration_seconds,
            error_message=error_message,
        )
        log.info(f"Session de suggestions {session_id} cloturee ({status})")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Impossible de cloturer la session {session_id}: {exc}")


@contextmanager
def suggestion_session(account_id: Optional[int], *, source: str,
                       config: Optional[Dict[str, Any]] = None):
    """Ouvrir la session, la rendre a l'appelant, la clore quoi qu'il arrive.

    Une passe interrompue par une exception est cloturee en ERROR plutot que laissee
    ACTIVE : une session qui ne finit jamais fausse autant les moyennes qu'une session
    manquante.
    """
    session_id = open_suggestion_session(account_id, source=source, config=config)
    started = time.time()
    status, error = "COMPLETED", None
    try:
        yield session_id
    except BaseException as exc:  # noqa: BLE001 — on requalifie puis on relaie
        status, error = "ERROR", str(exc)[:200]
        raise
    finally:
        close_suggestion_session(
            session_id, status=status,
            duration_seconds=int(time.time() - started),
            error_message=error,
        )


__all__ = [
    "SUGGESTION_TARGET_TYPE",
    "close_suggestion_session",
    "open_suggestion_session",
    "suggestion_session",
]
