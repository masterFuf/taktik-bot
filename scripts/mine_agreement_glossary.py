"""Find a writing model's gender-agreement mistakes by confronting it with a reference model.

WHY THIS EXISTS — `app/ai/glossary.py` suppresses the determiner mistakes a cheap model makes,
but it only covers words somebody noticed by hand. Three automatic detectors were built and
measured on 2026-09-09 and all three were net-negative: an LLM proofreader rewrote correct text,
a lower temperature kept the mistakes, and a determiner corrector fed by the model's own
out-of-context gender answers broke five correct comments out of six.

They failed for one reason: they asked a model to JUDGE a sentence after the fact. This script
asks nothing. It COUNTS what two models wrote when they were not being watched.

HOW IT DECIDES — the reference model (the one measured at zero hard mistakes) supplies a lexicon
of nouns whose gender never varies across its published output. Any determiner the target model
attaches against that lexicon is a mistake, and the correct form is already known. Measured on
427 target comments against 1 404 published reference comments: 7 contradictions in 436 covered
uses (1.6 %), no false positive, and it settled "vibe" — which the target's own inconsistency
(8 feminine, 4 masculine) could not.

WHAT IT DOES NOT DO — it never edits the glossary. It prints candidates for a human to accept,
because the one detector we measured as reliable is a person reading the output.

    python scripts/mine_agreement_glossary.py --db <path> --target corpus.json
    python scripts/mine_agreement_glossary.py --db <path> --self-check   # reference only
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

# Determiners that carry a gender, per language. DATA, not code: a language absent here is
# simply not mined, and its absence is visible rather than silently assumed to be safe.
DETERMINERS: Dict[str, Dict[str, str]] = {
    "fr": {"le": "m", "un": "m", "ce": "m", "cet": "m", "du": "m", "au": "m",
           "la": "f", "une": "f", "cette": "f"},
    "es": {"el": "m", "un": "m", "este": "m", "ese": "m",
           "la": "f", "una": "f", "esta": "f", "esa": "f"},
    "pt": {"o": "m", "um": "m", "este": "m", "esse": "m",
           "a": "f", "uma": "f", "esta": "f", "essa": "f"},
    "it": {"il": "m", "un": "m", "questo": "m", "quello": "m",
           "la": "f", "una": "f", "questa": "f", "quella": "f"},
    "nl": {"het": "het", "dit": "het", "dat": "het",
           "de": "de", "deze": "de", "die": "de"},
}

# The word after a determiner is not always a noun, and a PRE-NOMINAL ADJECTIVE is the trap that
# matters: "une super ambiance" and "un super moment" make `super` look like a noun written both
# ways. Measured on 1 404 published comments, the only two candidates produced without this list
# were `super` and `magnifique` — both adjectives, both wrong.
NON_NOUNS: Dict[str, set] = {
    "fr": {
        "dont", "que", "qui", "quoi", "est", "sont", "etait", "peut", "fait", "va", "meme",
        "plus", "moins", "tres", "bien", "mal", "tout", "toute", "autre", "seul", "seule",
        "super", "magnifique", "beau", "bel", "belle", "grand", "grande", "petit", "petite",
        "joli", "jolie", "nouveau", "nouvel", "nouvelle", "premier", "premiere", "dernier",
        "derniere", "vrai", "vraie", "bon", "bonne", "mauvais", "mauvaise", "long", "longue",
        "gros", "grosse", "jeune", "vieux", "vieille", "double", "simple", "pur", "pure",
        "leger", "legere", "immense", "enorme", "incroyable", "parfait", "parfaite",
        "genre", "cote", "type", "sorte", "espece", "peu", "tas", "max", "top",
        # Ordinals take the gender of whatever they qualify ("au deuxieme plan" against
        # "la deuxieme photo"), so they look like a noun written both ways. Same trap as
        # the pre-nominal adjectives above, found on a 943-comment run.
        "deuxieme", "troisieme", "quatrieme", "cinquieme", "sixieme", "septieme",
        "huitieme", "neuvieme", "dixieme", "enieme", "seconde", "second",
    },
}

# The reference admits UNANIMITY only. A noun the reference model itself wrote both ways proves
# nothing about the target, and a threshold below 100 % would launder the reference's own slips
# into rules the target is judged against.
MIN_REFERENCE_USES = 3
MIN_SELF_USES = 4


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def pairs(texts: Iterable[str], language: str = "fr") -> Iterator[Tuple[str, str, str]]:
    """Every (noun, gender its determiner carries, the written form) in `texts`."""
    determiners = DETERMINERS.get(language)
    if not determiners:
        return
    pattern = re.compile(
        r"\b(" + "|".join(sorted(determiners, key=len, reverse=True)) + r")\s+([a-z]{3,20})\b"
    )
    excluded = NON_NOUNS.get(language, set())
    for text in texts:
        for determiner, noun in pattern.findall(_fold(text)):
            if noun in excluded or noun in determiners:
                continue
            yield noun, determiners[determiner], f"{determiner} {noun}"


def reference_lexicon(texts: Iterable[str], language: str = "fr") -> Dict[str, Tuple[str, int, str]]:
    """Nouns whose gender NEVER varies in the reference output, with their commonest form."""
    genders: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    forms: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for noun, gender, written in pairs(texts, language):
        genders[noun][gender] += 1
        forms[noun][written] += 1
    return {
        noun: (next(iter(counter)), sum(counter.values()), forms[noun].most_common(1)[0][0])
        for noun, counter in genders.items()
        if sum(counter.values()) >= MIN_REFERENCE_USES and len(counter) == 1
    }


def _published(db: Path, language: str) -> List[str]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [row[0] for row in connection.execute(
            "SELECT comment_text FROM posted_comments "
            "WHERE source='ai' AND comment_text <> '' AND COALESCE(language,?)=?",
            (language, language),
        )]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True,
                        help="taktik-data.db — supplies the reference corpus (published comments)")
    parser.add_argument("--target", type=Path,
                        help="JSON list of comments written by the model being audited")
    parser.add_argument("--language", default="fr")
    parser.add_argument("--self-check", action="store_true",
                        help="report the reference model's own inconsistencies instead")
    args = parser.parse_args()

    reference_texts = _published(args.db, args.language)
    reference = reference_lexicon(reference_texts, args.language)
    print(f"reference : {len(reference_texts)} published comments -> "
          f"{len(reference)} nouns with an invariable gender")

    if args.self_check or not args.target:
        counts: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for noun, gender, written in pairs(reference_texts, args.language):
            counts[noun][written] += 1
        wobbly = [(n, c) for n, c in counts.items()
                  if sum(c.values()) >= MIN_SELF_USES
                  and len({DETERMINERS[args.language][w.split()[0]] for w in c}) > 1]
        print(f"\nthe reference contradicts ITSELF on {len(wobbly)} nouns "
              f"— these cannot serve as rules:")
        for noun, counter in sorted(wobbly, key=lambda x: -sum(x[1].values()))[:20]:
            print(f"   {noun:<18}{dict(counter)}")
        return 0

    target = json.loads(args.target.read_text(encoding="utf-8"))
    print(f"target    : {len(target)} comments ({args.target})\n")

    contradicted: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    agreed = 0
    unknown: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for noun, gender, written in pairs(target, args.language):
        if noun not in reference:
            unknown[noun][gender] += 1
        elif gender == reference[noun][0]:
            agreed += 1
        else:
            contradicted[noun][written] += 1

    wrong = sum(sum(c.values()) for c in contradicted.values())
    covered = agreed + wrong
    print(f"uses covered by the reference : {covered}")
    print(f"   agreeing      {agreed}")
    print(f"   CONTRADICTING {wrong}  ({100 * wrong / max(covered, 1):.1f} %)\n")

    if contradicted:
        print("GLOSSARY CANDIDATES — the correct form is the reference's, review before adding:")
        for noun, written in sorted(contradicted.items(), key=lambda x: -sum(x[1].values())):
            correct = reference[noun][2]
            seen = ", ".join(f"{form!r}x{n}" for form, n in written.most_common())
            print(f'   {correct:<20} <- wrote {seen}   '
                  f'(reference: {reference[noun][1]} uses)')

    loose = [(n, c) for n, c in unknown.items()
             if sum(c.values()) >= MIN_SELF_USES and len(c) > 1]
    if loose:
        print(f"\nOUTSIDE THE REFERENCE, the target contradicts itself ({len(loose)}) "
              f"— no correct form known, arbitrate by hand:")
        for noun, counter in sorted(loose, key=lambda x: -sum(x[1].values()))[:15]:
            print(f"   {noun:<18}{dict(counter)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
