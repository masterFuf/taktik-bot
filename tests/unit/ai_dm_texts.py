"""One text per reason the rule of a DM written by an AI refuses, shared by the tests of its callers.

The rule is `taktik/core/ai/dm_rules.py`; the cold DM, the DM reply and the welcome DM each prove
that every one of these texts stops before the phone. The account they are written for writes in
French (`FRENCH_ACCOUNT`, the payload block) and forbids `gratuit`.
"""
from __future__ import annotations

import pytest

#: The `aiDmRules` block of the payload: a French account, no link allowed, one forbidden term.
FRENCH_ACCOUNT = {"linksAllowed": False, "forbiddenTerms": ["gratuit"],
                  "accountProfile": {"language": "fr"}}

#: A text within the rules for that account.
WITHIN_RULES = "Bonjour Léa, ta boulangerie a l'air superbe, on en parle ?"

#: reason -> a text that breaks only that rule, for that account.
BROKEN_TEXTS = {
    "too_short": "Salut, ça va ?",
    "too_long": "Bonjour " + "a" * 500,
    "language": "Hello Lea, your bakery looks amazing, could we talk about it?",
    "link": "Bonjour, va voir maboutique.fr pour la suite, merci",
    "email": "Bonjour, écris-moi sur lea@exemple.fr pour en parler",
    "phone": "Bonjour, appelle-moi au 06 12 34 56 78 quand tu veux",
    "forbidden_term": "Bonjour, c'est gratuit pour toi pendant un mois entier",
}

#: `@pytest.mark.parametrize("reason, text", EACH_REASON)`.
EACH_REASON = [pytest.param(reason, text, id=reason) for reason, text in BROKEN_TEXTS.items()]
