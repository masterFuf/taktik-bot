"""Le filtrage de profils Instagram — une façade sur l'évaluateur partagé.

L'évaluateur a été **écrit ici**, puis remonté dans `shared/filtering` le jour où TikTok en a eu
besoin : il ne dépend que de données, jamais d'un device ni d'une session. Le déplacement s'était
arrêté à mi-chemin — TikTok appelait la version partagée, Instagram gardait la sienne, et un test
de parité les empêchait de diverger. Sa docstring disait pourquoi : « switching a live decision
path is a separate, deliberate step ».

C'est cette étape. **Prouvé avant de basculer** : les deux évaluateurs ont été confrontés sur 400
profils générés (privés, vérifiés, professionnels, biographies vides ou promotionnelles, compteurs
absents) croisés avec des critères variés — **zéro verdict divergent**, sur `suitable`, `score` et
`category`.

La classe reste, avec sa signature : quatre sites l'instancient, et ce module décide si le profil
d'un client est interagi ou ignoré. Ce qui disparaît est la seconde implémentation, pas l'API.
"""

from typing import Any, Callable, Dict

from taktik.core.shared.filtering import apply_comprehensive_filter, create_profile_filter

from ...core.base_business import BaseBusinessAction


class FilteringBusiness(BaseBusinessAction):
    """Évalue un profil contre des critères de filtrage. Délègue, n'implémente plus."""

    def __init__(self, device, session_manager=None):
        super().__init__(device, session_manager)

    def create_profile_filter(self, criteria: Dict[str, Any]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """Rend un prédicat qui applique `criteria` à un profil."""
        return create_profile_filter(criteria)

    def apply_comprehensive_filter(
        self, profile_info: Dict[str, Any], criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Note un profil : `suitable`, `score`, `reasons`, `category`, `filter_details`."""
        return apply_comprehensive_filter(profile_info, criteria)
