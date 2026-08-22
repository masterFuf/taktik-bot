"""Replay already-paid AI calls on other models, and compare — for the price of a coffee.

Changing the model is a product decision, not a pricing one: a classifier that is 60 % cheaper
and picks the wrong niche costs far more than it saves, and a comment that reads like a bot
costs the account. The only honest way to decide is to replay calls we ALREADY paid for, on
real data, and look at what comes back.

Everything needed is already stored:

  - `profile_qualification` keeps the model's raw JSON output (`ai_classification`) for 23k+
    profiles, and `ai_screenshots` keeps the very screenshot each one was classified from;
  - `posted_comments` keeps the caption, the post description, the comment that went out, the
    model that wrote it and what it cost.

So a replay needs no device, no run and no session — just the same inputs through the same
production functions with a different model name.

WHAT IT DOES NOT DO: judge the comments. A comment is a matter of voice and taste, and an LLM
judge would cost as much as the test while replacing the only opinion that counts. Comments are
printed side by side; the profile classifications ARE scored automatically, because a taxonomy
is a closed vocabulary and agreement is a fact.

Usage
-----
    # See what it would cost — no API call, no spend:
    python scripts/eval/replay_models.py --profiles 50 --comments 50 \
        --models google/gemini-3.1-flash-lite,openai/gpt-5.6-luna

    # Actually run it, never spending more than $1:
    OPENROUTER_API_KEY=sk-or-... python scripts/eval/replay_models.py \
        --profiles 50 --comments 50 --models ... --taxonomy niche_taxonomy.json \
        --run --budget 1.0

The budget is enforced on the cost OpenRouter itself reports for each call (captured through the
same `ai_spend` event production uses), not on an estimate: the run stops the moment the ceiling
is reached, mid-model if need be, and everything already obtained is written out.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# The bot's own modules — this script drives PRODUCTION code paths. A local reimplementation of
# the prompt would benchmark the reimplementation.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from taktik.core.app.ai.factory import build_ai_service  # noqa: E402
from taktik.core.database.ai_benchmark import AIBenchmark  # noqa: E402

# Cost of one replayed call on the reference model, measured on the production ledger over
# 2026-08-20..22 (1 799 profiles, 107 comments). Used ONLY for the dry-run estimate; the real
# ceiling is enforced against what OpenRouter bills per call.
REFERENCE_PROFILE_USD = 0.00114  # no prompt-cache hit on a replay: the prefix is billed in full
REFERENCE_COMMENT_USD = 0.00100
REFERENCE_MODEL_IN_PER_M = 0.25
REFERENCE_MODEL_OUT_PER_M = 1.50

DEFAULT_DB = Path(os.environ.get("APPDATA", "")) / "taktik-desktop" / "taktik-data.db"


class SpendCapture:
    """A stand-in for the bridge IPC that keeps the money and drops the rest.

    `AIService` reports every paid call through `ipc.ai_spend(cost, model=, label=, kind=)` — the
    single point production uses for its ledger. Capturing it here means the budget is enforced
    on what was ACTUALLY billed, and that a model whose price changed overnight cannot quietly
    overrun an estimate. Every other IPC method (`ai_profile_done`, card events…) is answered
    with a no-op so a production path never breaks for lack of a bridge.
    """

    def __init__(self) -> None:
        self.total_usd = 0.0
        self.calls = 0
        self.by_kind: Dict[str, float] = defaultdict(float)

    def ai_spend(self, cost: float, model: str = "", label: str = "", kind: str = "other") -> None:
        try:
            value = float(cost)
        except (TypeError, ValueError):
            return
        self.total_usd += value
        self.calls += 1
        self.by_kind[kind] += value

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class BudgetExceeded(Exception):
    """Raised the moment the ceiling is crossed — the caller writes out and stops."""


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Write one result NOW, not at the end.

    A benchmark is stopped mid-way for the most ordinary reason there is: you look at the first
    numbers and decide you have seen enough. Buffering everything until the last line means that
    decision throws away every call already paid for — which happened, on the run that produced
    this function. Appending costs nothing and makes an interrupted run worth exactly what it
    cost.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def sample_profiles(conn: sqlite3.Connection, count: int, seed: int) -> List[sqlite3.Row]:
    """`count` classified profiles that still have their screenshot, SPREAD ACROSS NICHES.

    Taking the last N rows would take one run's worth of profiles — on this base, fifty
    watercolour illustrators in a row. A model that handles art and fails at restaurants would
    score perfectly. So the sample is stratified: whole pool, shuffled with a fixed seed, then
    capped per niche so no single niche can own the result.
    """
    rows = conn.execute(
        """
        SELECT q.username, q.ai_classification, q.niche_slug, q.sub_niche_slug,
               q.ai_profession, q.ai_gender, q.ai_age_group, q.ai_account_based_in,
               s.image_data,
               p.biography, p.business_category, p.website,
               p.followers_count, p.following_count, p.posts_count,
               p.is_private, p.is_verified
        FROM profile_qualification q
        JOIN ai_screenshots s ON s.filename = 'ai_' || q.username || '.jpg'
        LEFT JOIN social_profiles p
               ON p.platform = 'instagram' AND lower(p.username) = lower(q.username)
        WHERE q.platform = 'instagram'
          AND q.ai_classification IS NOT NULL AND q.ai_classification <> ''
          AND q.niche_slug IS NOT NULL AND q.niche_slug <> ''
        """
    ).fetchall()

    random.Random(seed).shuffle(rows)
    per_niche = max(1, count // 8)
    picked: List[sqlite3.Row] = []
    used: Dict[str, int] = defaultdict(int)
    for row in rows:
        niche = row["niche_slug"]
        if used[niche] >= per_niche:
            continue
        picked.append(row)
        used[niche] += 1
        if len(picked) >= count:
            break
    # A base with few niches would starve the sample; top it up in shuffled order.
    if len(picked) < count:
        seen = {row["username"] for row in picked}
        picked.extend(row for row in rows if row["username"] not in seen)
    return picked[:count]


def sample_comments(conn: sqlite3.Connection, count: int, seed: int) -> List[sqlite3.Row]:
    """`count` comments that actually went out, with the context they were written from."""
    rows = conn.execute(
        """
        SELECT target_username, post_author, post_caption, post_description,
               comment_text, ai_model, language, posted_at, account_id
        FROM posted_comments
        WHERE platform = 'instagram' AND kind = 'comment'
          AND comment_text IS NOT NULL AND comment_text <> ''
          AND (post_caption IS NOT NULL AND post_caption <> '')
        """
    ).fetchall()
    random.Random(seed).shuffle(rows)
    return rows[:count]


def load_persona(conn: sqlite3.Connection, username: str) -> Optional[Dict[str, Any]]:
    """The voice of ONE named account, in the shape `generate_smart_comment` expects.

    Named explicitly rather than joined from the comment, because the join does not hold: on this
    base `posted_comments.account_id` (and `sessions_unified.account_id` with it) carries ids that
    exist in `social_profiles`, not in `accounts` — 621 of 625 comments and every recent
    interaction point at nothing. Resolving a persona through that would have quietly dressed
    every replayed comment in the wrong account's voice, or in none, and the benchmark would have
    been judging the wrong thing.

    Without it, comments are replayed generic — fair between models, but not what actually goes
    out. The run says which of the two it did.
    """
    if not username:
        return None
    try:
        row = conn.execute(
            """
            SELECT display_name, niche, product_service, objective, tone_personality,
                   unique_selling_point, custom_context, preferred_language
            FROM accounts WHERE lower(username) = lower(?) LIMIT 1
            """,
            (username,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    persona = {
        "displayName": row["display_name"] or "",
        "niche": row["niche"] or "",
        "productService": row["product_service"] or "",
        "objective": row["objective"] or "",
        "tonePersonality": row["tone_personality"] or "",
        "uniqueSellingPoint": row["unique_selling_point"] or "",
        "customContext": row["custom_context"] or "",
        "language": row["preferred_language"] or "",
    }
    return persona if any(persona.values()) else None
    for row in rows:
        persona = {
            "displayName": row["display_name"] or "",
            "niche": row["niche"] or "",
            "productService": row["product_service"] or "",
            "objective": row["objective"] or "",
            "tonePersonality": row["tone_personality"] or "",
            "uniqueSellingPoint": row["unique_selling_point"] or "",
            "customContext": row["custom_context"] or "",
            "language": row["preferred_language"] or "",
        }
        if any(persona.values()):
            personas[row["id"]] = persona
    return personas


def write_screenshots(rows: List[sqlite3.Row], out_dir: Path) -> Dict[str, Path]:
    """Materialise the stored images — the vision call takes a path, not bytes.

    `ai_screenshots.image_data` is TEXT holding base64, not a binary blob: the column doubles as
    the cross-PC sync transport, and base64 is what survives that trip. A raw `write_bytes` of it
    would write the base64 alphabet into a .jpg and every vision call would fail on an unreadable
    image. Binary is still accepted, for a base that stores it that way.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}
    for row in rows:
        data = row["image_data"]
        if not data:
            continue
        if isinstance(data, str):
            try:
                data = base64.b64decode(data, validate=False)
            except Exception:  # noqa: BLE001 — a single unreadable image is not a reason to stop
                continue
        path = out_dir / f"ai_{row['username']}.jpg"
        path.write_bytes(data)
        paths[row["username"]] = path
    return paths


def profile_context_of(row: sqlite3.Row) -> Dict[str, Any]:
    """The text hints production sends ALONGSIDE the screenshot.

    `classify_profile_niche` reads `biography`, `business_category` and the counts out of this
    dict and puts them in the prompt. Replaying with the screenshot alone asks the candidate model
    a harder question than the one the stored answer was given — every disagreement would then be
    the missing bio, not the model. The fields come from `social_profiles`, which is where the run
    had read them too.
    """
    context: Dict[str, Any] = {}
    for key, column in (
        ("biography", "biography"),
        ("business_category", "business_category"),
        ("website", "website"),
    ):
        value = row[column] if column in row.keys() else None
        if value:
            context[key] = value
    for key in ("followers_count", "following_count", "posts_count"):
        value = row[key] if key in row.keys() else None
        if value is not None:
            context[key] = value
    for key in ("is_private", "is_verified"):
        value = row[key] if key in row.keys() else None
        if value is not None:
            context[key] = bool(value)
    return context


def service_on(model: str, api_key: str, spend: SpendCapture, taxonomy: Optional[Dict[str, list]]):
    """An AIService that actually calls `model`.

    `build_ai_service(vision_model=..., text_model=...)` does NOT honour those arguments: since
    the two-fixed-models migration the constructor overwrites them with `MODEL_ANALYSIS` /
    `MODEL_GENERATION` and its own comment says they are "ignored". Passing them therefore
    benchmarks the model we already use — 50 calls, a real bill, and a table of zeroes that looks
    like the candidate model failing when nothing of the sort happened.

    The models are attributes on the instance, so the honest injection is to set them after
    construction. Nothing in production reads them from anywhere else; the constants stay the
    single source for every real run.
    """
    service = build_ai_service(api_key=api_key, ipc=spend, niche_taxonomy=taxonomy)
    service.model_analysis = model
    service.model_generation = model
    # Display aliases some call sites read for their labels — kept in step so a log line never
    # names a model that was not called.
    service.vision_model = model
    service.text_model = model
    return service


def unwrap(answer: Dict[str, Any]) -> Dict[str, Any]:
    """The classification itself, out of the envelope the service returns.

    `classify_profile_niche` answers `{success, classification: {...}, model, cost_usd, ...}`.
    Comparing the envelope compares `niche_category` against nothing at all, which scores every
    model at 0 % — the fields are simply one level down.
    """
    inner = answer.get("classification")
    return inner if isinstance(inner, dict) else answer


def field(payload: Dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    return str(value).strip().lower()


def compare_classification(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, bool]:
    """Field-by-field agreement with what is already stored.

    The baseline is not a truth — it is what the production model answered and what the app has
    been acting on since. Agreement therefore reads as "would behave the same", which is the
    question being asked, and a disagreement is a row to go and look at, not a verdict.
    """
    return {
        "niche_category": field(baseline, "niche_category") == field(candidate, "niche_category"),
        "niche": field(baseline, "niche") == field(candidate, "niche"),
        "profession": field(baseline, "profession") == field(candidate, "profession"),
        "gender": field(baseline, "gender") == field(candidate, "gender"),
        "age_group": field(baseline, "age_group") == field(candidate, "age_group"),
        "country": field(baseline, "country") == field(candidate, "country"),
        "language": field(baseline, "language") == field(candidate, "language"),
    }


def replay_profiles(
    model: str,
    rows: List[sqlite3.Row],
    shots: Dict[str, Path],
    taxonomy: Optional[Dict[str, list]],
    api_key: str,
    spend: SpendCapture,
    budget: float,
    sink: Path,
    run_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Classify each sampled profile again, on `model`, through the production entry point."""
    service = service_on(model, api_key, spend, taxonomy)
    results: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        username = row["username"]
        shot = shots.get(username)
        if not shot:
            continue
        if spend.total_usd >= budget:
            raise BudgetExceeded(f"budget reached before profile {index}/{len(rows)}")

        before = spend.total_usd
        started = time.time()
        try:
            answer = service.classify_profile_niche(
                username=username,
                screenshot_path=str(shot),
                profile_context=profile_context_of(row),
                response_language="fr",
                platform="instagram",
            ) or {}
        except Exception as exc:  # noqa: BLE001 — one bad profile must not end the benchmark
            answer = {"error": str(exc)}

        baseline = json.loads(row["ai_classification"] or "{}")
        candidate = unwrap(answer)
        record = {
            "username": username,
            "model": model,
            # What the service says it CALLED, not what we asked for: a benchmark that cannot
            # prove which model answered is not a benchmark.
            "served_model": answer.get("model"),
            "usd": round(spend.total_usd - before, 6),
            "seconds": round(time.time() - started, 2),
            "baseline": baseline,
            "candidate": candidate,
            "agreement": compare_classification(baseline, candidate) if "error" not in answer else {},
        }
        results.append(record)
        append_jsonl(sink, record)
        AIBenchmark.record(
            run_id=run_id, task="profile", case_ref=username, model=model,
            served_model=record["served_model"], cost_usd=record["usd"], seconds=record["seconds"],
            baseline=baseline, candidate=candidate, agreement=record["agreement"],
        )
        print(f"  [{model}] {index}/{len(rows)} @{username} · ${spend.total_usd:.4f}", flush=True)
    return results


def replay_comments(
    model: str,
    rows: List[sqlite3.Row],
    persona: Optional[Dict[str, Any]],
    api_key: str,
    spend: SpendCapture,
    budget: float,
    sink: Path,
    run_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Write each sampled comment again, on `model`, from the same post context."""
    service = service_on(model, api_key, spend, None)
    results: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if spend.total_usd >= budget:
            raise BudgetExceeded(f"budget reached before comment {index}/{len(rows)}")

        before = spend.total_usd
        started = time.time()
        try:
            answer = service.generate_smart_comment(
                post_description=row["post_description"] or "",
                username=row["post_author"] or row["target_username"] or "",
                post_caption=row["post_caption"] or "",
                language=row["language"] or "auto",
                account_persona=persona,
                platform="instagram",
            ) or {}
        except Exception as exc:  # noqa: BLE001
            answer = {"error": str(exc)}

        record = {
            "target": row["target_username"],
            "model": model,
            "persona": bool(persona),
            "usd": round(spend.total_usd - before, 6),
            "seconds": round(time.time() - started, 2),
            "caption": (row["post_caption"] or "")[:300],
            "original": row["comment_text"],
            "original_model": row["ai_model"],
            "candidate": answer.get("comment") or answer.get("text") or answer.get("error") or "",
        }
        results.append(record)
        append_jsonl(sink, record)
        AIBenchmark.record(
            run_id=run_id, task="comment", case_ref=row["target_username"] or "", model=model,
            served_model=answer.get("model"), cost_usd=record["usd"], seconds=record["seconds"],
            baseline={"comment": record["original"], "model": record["original_model"], "caption": record["caption"]},
            candidate={"comment": record["candidate"], "persona": record["persona"]},
        )
        print(f"  [{model}] {index}/{len(rows)} @{row['target_username']} · ${spend.total_usd:.4f}", flush=True)
    return results


def estimate(
    profile_models: List[str],
    comment_models: List[str],
    profiles: int,
    comments: int,
    prices: Dict[str, Dict[str, float]],
) -> None:
    """What this would cost, per model, before a single call is made.

    The two lists are counted SEPARATELY: a model asked only for comments must not be billed for
    fifty profiles it will never see. Getting that wrong overstates the estimate by two thirds —
    on the one script whose entire purpose is to answer "what is this going to cost me".
    """
    print(f"\nDry run — nothing was called, nothing was spent.\n")
    print(f"{'model':<38} {'profiles':>10} {'comments':>10} {'total':>10}")
    print("-" * 70)
    grand = 0.0
    for model in dict.fromkeys(profile_models + comment_models):
        price = prices.get(model)
        if price:
            ratio_in = price["in"] / REFERENCE_MODEL_IN_PER_M
            ratio_out = price["out"] / REFERENCE_MODEL_OUT_PER_M
            ratio = (ratio_in * 0.6) + (ratio_out * 0.4)  # the measured input/output split
        else:
            ratio = 1.0
        p = profiles * REFERENCE_PROFILE_USD * ratio if model in profile_models else 0.0
        c = comments * REFERENCE_COMMENT_USD * ratio if model in comment_models else 0.0
        grand += p + c
        suffix = "" if price else "   (price unknown — counted at the reference rate)"
        print(f"{model:<38} {p:>9.3f}$ {c:>9.3f}$ {p + c:>9.3f}${suffix}")
    print("-" * 70)
    print(f"{'TOTAL':<38} {'':>10} {'':>10} {grand:>9.3f}$")
    print("\nRe-run with --run and a --budget to execute.\n")


def fetch_prices(models: List[str]) -> Dict[str, Dict[str, float]]:
    """Live per-million prices from OpenRouter's public catalogue. No key, no cost."""
    try:
        import urllib.request

        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as response:
            catalogue = json.loads(response.read().decode("utf-8")).get("data", [])
    except Exception as exc:  # noqa: BLE001 — the estimate is a courtesy, not a requirement
        print(f"(could not read the price catalogue: {exc})")
        return {}
    wanted = set(models)
    prices: Dict[str, Dict[str, float]] = {}
    for entry in catalogue:
        if entry.get("id") in wanted:
            pricing = entry.get("pricing") or {}
            prices[entry["id"]] = {
                "in": float(pricing.get("prompt") or 0) * 1e6,
                "out": float(pricing.get("completion") or 0) * 1e6,
            }
    return prices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="taktik-data.db (read-only)")
    parser.add_argument("--profiles", type=int, default=50, help="profiles to replay per model")
    parser.add_argument("--comments", type=int, default=50, help="comments to replay per model")
    parser.add_argument("--models", required=True, help="comma-separated OpenRouter model ids")
    parser.add_argument("--comment-models", default="", help="different model list for comments")
    parser.add_argument("--taxonomy", type=Path, help="premium niche taxonomy JSON (front-owned)")
    parser.add_argument("--out", type=Path, default=Path("eval-out"), help="where results are written")
    parser.add_argument("--seed", type=int, default=20260822, help="sampling seed — same seed, same sample")
    parser.add_argument("--note", default="", help="why this run exists — shown in the app")
    parser.add_argument("--persona-account", default="",
                        help="username of OUR account whose voice the comments must be written in")
    parser.add_argument("--budget", type=float, default=1.0, help="hard ceiling in USD")
    parser.add_argument("--run", action="store_true", help="actually call the models")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    comment_models = [m.strip() for m in args.comment_models.split(",") if m.strip()] or models

    if not args.db.exists():
        print(f"Database not found: {args.db}")
        return 1

    if not args.run:
        every = list(dict.fromkeys(models + comment_models))
        estimate(models, comment_models, args.profiles, args.comments, fetch_prices(every))
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if len(api_key) < 10:
        print("OPENROUTER_API_KEY is not set — refusing to run.")
        return 1

    taxonomy = None
    if args.taxonomy and args.taxonomy.exists():
        taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
        print(f"Taxonomy: {len(taxonomy)} categories, {sum(len(v) for v in taxonomy.values())} sub-niches")
    else:
        print("No taxonomy given — the classifier will answer free-form, as the standalone bot does.")

    conn = connect(args.db)
    profile_rows = sample_profiles(conn, args.profiles, args.seed) if args.profiles else []
    comment_rows = sample_comments(conn, args.comments, args.seed) if args.comments else []
    persona = load_persona(conn, args.persona_account) if comment_rows else None
    conn.close()
    niches = sorted({row["niche_slug"] for row in profile_rows})
    print(f"Sample: {len(profile_rows)} profiles across {len(niches)} niches, "
          f"{len(comment_rows)} comments (seed {args.seed})")
    print(f"  niches: {', '.join(niches)}")
    with_bio = sum(1 for row in profile_rows if (row["biography"] if "biography" in row.keys() else None))
    print(f"  context: {with_bio}/{len(profile_rows)} profiles replayed with their bio, as production sends it")

    if comment_rows:
        if persona:
            print(f"  persona: @{args.persona_account} — comments replayed in that account's voice")
        else:
            print("  persona: NONE — comments replayed generic. Pass --persona-account <username> "
                  "to judge what actually goes out.")

    args.out.mkdir(parents=True, exist_ok=True)
    shots = write_screenshots(profile_rows, args.out / "screenshots")

    profiles_sink = args.out / "profiles.jsonl"
    comments_sink = args.out / "comments.jsonl"
    # A fresh run starts fresh files; every result then lands as it is produced.
    for sink in (profiles_sink, comments_sink):
        if sink.exists():
            sink.unlink()

    # The run is opened BEFORE the first call: a benchmark interrupted half-way is then visible
    # in the app as an unfinished run carrying what it did pay for, not as nothing at all.
    run_id = AIBenchmark.start_run(
        seed=args.seed,
        sample_size=max(len(profile_rows), len(comment_rows)),
        budget_usd=args.budget,
        config={
            "tasks": [t for t, rows_ in (("profile", profile_rows), ("comment", comment_rows)) if rows_],
            "models": {"profile": models if profile_rows else [], "comment": comment_models if comment_rows else []},
            "profiles": len(profile_rows),
            "comments": len(comment_rows),
            "persona_account": args.persona_account or None,
            "taxonomy_categories": len(taxonomy) if taxonomy else 0,
        },
        note=args.note or None,
    )
    if run_id:
        print(f"Benchmark run #{run_id} — visible in the app's admin benchmark page")

    spend = SpendCapture()
    profile_results: List[Dict[str, Any]] = []
    comment_results: List[Dict[str, Any]] = []
    stopped = None

    try:
        for model in models:
            print(f"\n== profiles · {model} ==")
            profile_results.extend(
                replay_profiles(model, profile_rows, shots, taxonomy, api_key, spend, args.budget, profiles_sink, run_id)
            )
        for model in comment_models:
            print(f"\n== comments · {model} ==")
            comment_results.extend(
                replay_comments(model, comment_rows, persona, api_key, spend, args.budget, comments_sink, run_id)
            )
    except BudgetExceeded as exc:
        stopped = str(exc)
        print(f"\nSTOPPED: {exc}")
    except KeyboardInterrupt:
        stopped = "interrupted by the operator"
        print("\nSTOPPED: interrupted")
    finally:
        AIBenchmark.finish_run(
            run_id=run_id,
            status="stopped" if stopped else "completed",
            total_cost_usd=spend.total_usd,
        )

    print("\n=== agreement with what is already stored ===")
    print(f"{'model':<38} {'n':>4} {'category':>9} {'niche':>7} {'gender':>7} {'age':>6} {'country':>8} {'$':>8}")
    by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for result in profile_results:
        by_model[result["model"]].append(result)
    for model, results in by_model.items():
        scored = [r for r in results if r["agreement"]]
        if not scored:
            continue
        def rate(key: str) -> str:
            return f"{100 * sum(1 for r in scored if r['agreement'].get(key)) / len(scored):.0f}%"
        cost = sum(r["usd"] for r in results)
        print(f"{model:<38} {len(scored):>4} {rate('niche_category'):>9} {rate('niche'):>7} "
              f"{rate('gender'):>7} {rate('age_group'):>6} {rate('country'):>8} {cost:>7.4f}$")

    print(f"\nSpent: ${spend.total_usd:.4f} over {spend.calls} calls "
          f"({', '.join(f'{k} ${v:.4f}' for k, v in sorted(spend.by_kind.items()))})")
    if stopped:
        print(f"Incomplete: {stopped}")
    print(f"Results: {profiles_sink} · {comments_sink}")
    print("Comments are NOT scored — read them side by side, that call is yours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
