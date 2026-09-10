"""Rebuild `app/ai/data/agreement_fr.tsv` from Lexique plus our own corpus.

A noun ships only when TWO INDEPENDENT AUTHORITIES agree on its gender. That rule is the whole
design, and it comes from measurement rather than caution:

- asking the generation model itself broke five correct comments out of six;
- Lexique alone still broke correct French, always on the same family — clipped words and
  anglicisms whose modern usage fixed a gender the lexicographic entry does not know
  ("la box", "la typo", "une french");
- the two together corrected 4 of 1 370 generated comments and damaged none.

The big source stays OUT of the repository (Lexique383.tsv is 26 MB); only the validated
result ships, which is a few hundred nouns and 8 KB.

    python scripts/build_agreement_lexicon.py \\
        --lexique ~/Downloads/Lexique383.tsv \\
        --db "%APPDATA%/taktik-desktop/taktik-data.db"

Lexique 3.83 is CC BY-SA 4.0 (Boris New, Christophe Pallier — http://www.lexique.org), so the
generated file is a derivative under the same terms. The header written into it says so.
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mine_agreement_glossary import _corpora, merged_lexicon  # noqa: E402

OUT = ROOT / "taktik" / "core" / "app" / "ai" / "data" / "agreement_fr.tsv"


def dictionary_genders(lexique: Path) -> Dict[str, str]:
    """Nouns Lexique commits to a gender for, and nothing else.

    Two exclusions do all the work, and neither needs a hand-kept list:

    A word that is ALSO something other than a noun is dropped — that is what removes `dont`,
    `super`, `magnifique` and the ordinals, every trap that used to be maintained by hand.

    A noun with two genders is dropped, and Lexique marks those itself by leaving the `genre`
    field EMPTY (`tour`, `mode`, `manche`, `page`). The resource states its own ambiguity more
    reliably than a rule of ours would have inferred it.
    """
    per_word = collections.defaultdict(lambda: {"genders": set(), "categories": set()})
    with lexique.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            word = (row.get("ortho") or "").strip().lower()
            if not word or len(word) < 2 or " " in word:
                continue
            category = (row.get("cgram") or "").strip()
            entry = per_word[word]
            entry["categories"].add(category)
            if category == "NOM":
                gender = (row.get("genre") or "").strip()
                if gender in ("m", "f"):
                    entry["genders"].add(gender)

    return {
        word: next(iter(entry["genders"]))
        for word, entry in per_word.items()
        if len(entry["genders"]) == 1 and not (entry["categories"] - {"NOM"})
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexique", type=Path, required=True,
                        help="Lexique383.tsv — http://www.lexique.org, CC BY-SA 4.0")
    parser.add_argument("--db", type=Path, required=True,
                        help="taktik-data.db — supplies the real-usage corpora")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    dictionary = dictionary_genders(args.lexique)
    corpora = _corpora(args.db, "fr")
    usage_lexicon, _ = merged_lexicon(corpora, "fr")
    usage = {word: entry[0] for word, entry in usage_lexicon.items()}

    agreed = {w: g for w, g in sorted(dictionary.items()) if usage.get(w) == g}
    disputed = {w: (dictionary[w], usage[w]) for w in dictionary
                if w in usage and usage[w] != dictionary[w]}

    print(f"dictionary : {len(dictionary)} nouns (Lexique)")
    print(f"real usage : {len(usage)} nouns "
          f"({sum(len(t) for t in corpora.values())} texts)")
    print(f"   AGREED   {len(agreed)}  -> shipped")
    print(f"   disputed {len(disputed)} -> dropped: "
          f"{', '.join(sorted(disputed)[:8])}")

    header = f"""# Grammatical gender of French nouns — the ones we are SURE of.
#
# A noun is here only when TWO independent authorities agree on it:
#
#   1. Lexique 3.83 (http://www.lexique.org), CC BY-SA 4.0, by Boris New and Christophe Pallier.
#      Nouns only, and only where Lexique itself commits to a gender — it leaves the field empty
#      for `tour`, `mode`, `manche`, `page`, which is how it states its own ambiguity. A word
#      that is also a verb, an adjective or a pronoun is excluded, which removes `dont`, `super`,
#      `magnifique` and the ordinals with no hand-kept list.
#
#   2. Our own corpus: {len(usage)} nouns whose gender never varies across the profile bios, post
#      captions and published comments in the base — French written by real people, now.
#
# The second authority removes the failures the dictionary alone produced: `box`, `typo` and
# `french` carry a gender in Lexique that modern usage contradicts, and correcting them
# fabricated a mistake. {len(disputed)} words were dropped that way.
#
# REGENERATE:  python scripts/build_agreement_lexicon.py --lexique <Lexique383.tsv> --db <db>
# Generated {datetime.date.today().isoformat()} · {len(agreed)} nouns
#
# THIS FILE IS A DERIVATIVE OF LEXIQUE 3.83 AND IS THEREFORE CC BY-SA 4.0.
"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(header)
        for word, gender in agreed.items():
            handle.write(f"{word}\t{gender}\n")
    print(f"\nwritten: {args.out} ({args.out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
