from taktik.core.social_media.instagram.ui.selectors.shell.blocking_states import (
    PROBLEMATIC_PAGE_SELECTORS,
)


def test_problematic_page_permission_allow_selectors_are_catalog_owned():
    """Le bouton d'autorisation vient du catalogue, et couvre le dialogue reellement servi.

    Le test epinglait la liste ENTIERE. Son nom dit pourtant ce qu'il protege : que ces selecteurs
    vivent dans le catalogue plutot qu'en dur dans le detecteur. Figer le contenu allait au-dela,
    et punissait tout enrichissement — c'est ce qui est arrive le 2026-09-03, quand la mesure sur
    appareil a montre que `com.android.packageinstaller` n'est le paquet des dialogues de
    permission sur AUCUN Pixel du parc (Android 12 et 16 servent
    `com.google.android.permissioncontroller`).

    Il verifie donc l'intention : une correspondance qui survit au changement de paquet, et les
    libelles des deux langues.
    """
    selectors = PROBLEMATIC_PAGE_SELECTORS.allow_permission_button_selectors

    # Une entree au moins doit reconnaitre le bouton quel que soit le paquet qui le sert.
    assert any(
        "permission_allow_button" in (s.get("resourceIdMatches") or "")
        for s in selectors
    ), "aucune correspondance partielle : un changement de paquet rendrait le bouton injoignable"

    # Et les libelles des deux langues restent, pour les surcouches sans identifiant exploitable.
    libelles = {s.get("text") for s in selectors}
    assert {"AUTORISER", "ALLOW", "Autoriser", "Allow"} <= libelles

    # Rien d'autre que des selecteurs : la liste reste une donnee, pas du code.
    assert all(isinstance(s, dict) and s for s in selectors)
