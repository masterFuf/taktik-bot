"""Texts a model wrote in another language than the one asked, shared by the tests of the rule.

The rule is `taktik/core/ai/written_language.py`; the comments, the replies and the profile
summaries each prove that these texts are refused. Shortened rewrites of real outputs the audit
of October 2026 found in a month of production, no name kept.
"""
from __future__ import annotations

#: French comments a model wrote where the prompt said "Write in English".
FRENCH_WHERE_ENGLISH_WAS_ASKED = (
    "une esthétique si douce pour fêter ça, c’est un vrai choix 🎂",
    "ce jeu de lumière dorée entre les pylônes est sublime 🌇",
    "la désaturation donne une texture brute très cinématique aux lignes des bateaux 🎞️",
    "la précision des détails capillaires fait toute la différence pour un rendu naturel",
    "la finesse des traits au regard est juste parfaite 🤍",
)

#: French profile summaries with ideographs inside, as one model wrote 363 of them in a month.
FRENCH_SUMMARIES_WITH_IDEOGRAPHS = (
    "Photographe de portrait basée au Luxembourg, son compte sert de portfolio pour展示 ses séances.",
    "Consultante en bien-être qui partage des conseils simples pour aider son audience à vivre plus轻.",
    "Coach sportif certifié qui propose des séances en个人 et en entreprise, avec ses offres du moment.",
)
