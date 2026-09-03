"""L'orchestration de la détection de langue, une fois pour les deux plateformes.

`language_engine` porte déjà le moteur de scoring — c'est la moitié qui avait été mutualisée.
L'autre moitié, l'orchestration autour de lui, était restée **en double** : sept fonctions dans
`instagram/ui/language.py` et sept dans `tiktok/ui/language.py`, dont quatre identiques caractère
pour caractère.

Ce qui différait légitimement était de la **donnée** — les vocabulaires `_FR_WORDS` / `_EN_WORDS`,
propres à chaque application. C'est exactement la distinction que l'invariant du projet énonce :
une différence de plateforme est une donnée, pas une branche de code.

**Trois leçons avaient été apprises d'un seul côté**, et la fusion les porte aux deux :

1. TikTok **dérivait** la liste des catalogues à optimiser depuis le barrel ; Instagram en tenait
   une liste **écrite à la main**. Mesuré avant de fusionner : la liste manuelle **ratait trois
   catalogues** (`DISCOVER_PEOPLE`, `FEED_SUGGESTIONS`, `SETTINGS`), dont les sélecteurs de l'autre
   langue n'étaient donc jamais filtrés — et elle en optimisait un **deux fois**, `POST_SELECTORS`
   étant un alias de `POST_DETAIL_SELECTORS`.
2. Instagram acceptait `override` contre `available_locales()` ; TikTok contre un `("en", "fr")`
   figé, qui aurait rejeté toute nouvelle locale.
3. Instagram enregistrait la langue forcée dans son état ; TikTok ne le faisait pas, si bien que
   `get_detected_language()` rendait `None` après un override.

**Le piège de ce regroupement, et sa réponse.** Chaque module portait son propre `_detected_lang`
global. Ils doivent rester **séparés** : un même téléphone peut afficher Instagram en français et
TikTok en anglais. L'état vit donc dans l'**instance** — une par plateforme — et non dans le
module. Une variable partagée aurait fait passer la langue d'une application à l'autre.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence

from loguru import logger

from taktik.core.shared.ui import language_engine as engine

log = logger.bind(module="shared.ui.language")

#: Une langue FAUSSE est pire que pas de langue : elle retire les bons sélecteurs, là où
#: « unknown » les garde tous. D'où un plancher de score ET une marge de ratio — une avance d'un
#: point à bas niveau ne suffit pas à trancher.
DEFAULT_MIN_SCORE = 3.0
DEFAULT_MIN_RATIO = 2.0


class LanguageDetection:
    """La détection de langue d'UNE plateforme, avec son vocabulaire et son état propre."""

    def __init__(
        self,
        platform: str,
        fr_words: Sequence[str],
        en_words: Sequence[str],
        *,
        min_score: float = DEFAULT_MIN_SCORE,
        min_ratio: float = DEFAULT_MIN_RATIO,
    ) -> None:
        self.platform = platform
        self.fr_words = fr_words
        self.en_words = en_words
        self.min_score = min_score
        self.min_ratio = min_ratio
        self._fr_patterns = engine.compile_vocabulary(fr_words)
        self._en_patterns = engine.compile_vocabulary(en_words)
        # Par INSTANCE, jamais par module : voir l'en-tête.
        self._detected_lang: Optional[str] = None

    # ── État ──────────────────────────────────────────────────────────────────

    def get_detected_language(self) -> Optional[str]:
        """La langue détectée, ou None tant que la détection n'a pas tourné."""
        return self._detected_lang

    def reset(self) -> None:
        """Remet l'état à zéro — ce qui compte entre deux comptes sur le même appareil."""
        self._detected_lang = None

    # ── Détection ─────────────────────────────────────────────────────────────

    def detect_language(self, device) -> str:
        """Détecte la langue de l'application depuis un seul dump. Rend 'en', 'fr' ou 'unknown'."""
        try:
            xml = engine.read_dump(device)
            if not xml:
                log.warning(f"No usable UI dump for {self.platform} language detection")
                self._detected_lang = "unknown"
                return self._detected_lang

            outcome = engine.decide(
                xml, self._fr_patterns, self._en_patterns,
                min_score=self.min_score, min_ratio=self.min_ratio,
            )
            self._detected_lang = outcome.language

            log.info(
                f"🌐 {self.platform} language detected: {self._detected_lang} "
                f"(FR={outcome.fr_score}, EN={outcome.en_score})"
            )
            if self._detected_lang == "unknown":
                log.info(
                    f"🌐 {self.platform} language undecided on this screen — keeping all locales "
                    f"({outcome.values_seen} visible strings; "
                    f"FR matched {outcome.fr_matched[:6] or 'nothing'}; "
                    f"EN matched {outcome.en_matched[:6] or 'nothing'})."
                )
            return self._detected_lang

        except Exception as exc:  # noqa: BLE001 — une détection ratée rend 'unknown', pas une erreur
            log.error(f"{self.platform} language detection failed: {exc}")
            self._detected_lang = "unknown"
            return self._detected_lang

    def redetect_if_unknown(self, device, optimize: Callable[[Any], str]) -> Optional[str]:
        """Retente la détection, mais SEULEMENT si la langue est encore indécise.

        La détection tourne une fois, sur l'écran que l'application montrait. Une langue déjà
        tranchée n'est jamais rouverte : un écran plus tardif ne pourrait que transformer une
        bonne réponse en une moins bonne. À l'inverse, un seul dump indécis laissait toute la
        session en mode union — d'où cette seconde chance, et elle seule.
        """
        if self._detected_lang not in (None, "unknown"):
            return self._detected_lang
        log.info(f"🌐 {self.platform} language still undecided — retrying on the current screen")
        return optimize(device)

    # ── Sélecteurs ────────────────────────────────────────────────────────────

    def classify_selector(self, xpath: str) -> str:
        return engine.classify_selector(xpath, self.fr_words, self.en_words)

    def filter_selectors(self, selectors: List[str], lang: str) -> List[str]:
        """Retire les sélecteurs visant l'autre langue. Une langue indécise les garde tous."""
        return engine.filter_selectors(selectors, lang, self.fr_words, self.en_words)

    def optimize_selector_dataclass(self, instance, lang: str) -> int:
        """Filtre en place chaque champ liste d'une dataclass de sélecteurs. Rend le compte retiré."""
        return engine.optimize_selector_dataclass(instance, lang, self.fr_words, self.en_words)

    # ── Point d'entrée ────────────────────────────────────────────────────────

    def detect_and_optimize(
        self,
        device,
        override: Optional[str],
        *,
        barrel,
        set_active_locale: Callable[[Optional[str]], Any],
        available_locales: Optional[Callable[[], Iterable[str]]] = None,
    ) -> str:
        """Détecte (ou force) la langue, puis optimise tous les catalogues de sélecteurs.

        À appeler une fois, tôt dans un workflow, après connexion et ouverture de l'application ;
        n'importe quel écran montrant la navigation du bas suffit.
        """
        if override:
            allowed = tuple(available_locales()) if available_locales else ("en", "fr")
            lang = override if override in allowed else "unknown"
            # Enregistré dans l'état : sans cela `get_detected_language()` rendait None après un
            # override, et un appelant croyait la détection jamais lancée.
            self._detected_lang = lang
            log.info(f"🌐 {self.platform} language override: {override!r} -> {lang}")
        else:
            lang = self.detect_language(device)

        # La surcouche : les sélecteurs migrés lisent leurs fragments dans la locale active.
        set_active_locale(lang if lang != "unknown" else None)

        if lang == "unknown":
            log.info(f"{self.platform}: language unknown — overlay union + no in-place filtering")
            return lang

        total = 0
        for name, instance in self._selector_singletons(barrel):
            try:
                removed = self.optimize_selector_dataclass(instance, lang)
                if removed:
                    log.debug(f"  • {name}: removed {removed} wrong-language selector(s)")
                total += removed
            except Exception as exc:  # noqa: BLE001 — un catalogue récalcitrant n'arrête pas le run
                log.warning(f"  • {name}: optimization failed ({exc})")

        log.info(
            f"✅ {self.platform} selectors optimized for '{lang}' "
            f"({total} wrong-language selector(s) removed)"
        )
        return lang

    @staticmethod
    def _selector_singletons(barrel) -> List[tuple]:
        """Les catalogues à optimiser, DÉRIVÉS du barrel plutôt qu'énumérés.

        Une liste écrite à la main est une seconde description des mêmes objets, à côté du `__all__`
        du barrel. Celle d'Instagram avait vieilli exactement comme on s'y attend : trois catalogues
        absents, et un compté deux fois parce qu'il est un alias d'un autre.

        Les façades sont écartées par construction : `is_dataclass` est faux pour elles, et
        optimiser une façade passerait par son `__getattr__` sur un attribut fantôme.
        """
        out: List[tuple] = []
        seen: set = set()
        for name in getattr(barrel, "__all__", ()):
            if not name.endswith("SELECTORS"):
                continue
            obj = getattr(barrel, name, None)
            if obj is None or not is_dataclass(obj) or id(obj) in seen:
                continue
            seen.add(id(obj))
            out.append((type(obj).__name__, obj))
        return out


__all__ = ["LanguageDetection", "DEFAULT_MIN_SCORE", "DEFAULT_MIN_RATIO"]
