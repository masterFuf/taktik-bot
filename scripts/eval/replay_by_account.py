"""Replay what OUR accounts asked of the AI, account by account, on several models, and judge it.

`replay_models.py` answers "would another model behave like the one in production"; this answers
"which model does the job best for THIS account, and at what cost". Same inputs, same production
functions, but the sample is drawn per operated account and every answer is scored against a
reference instead of against what production happened to say.

Two tasks, the two where a model choice changes what goes out:

  - `profile`: the profiles THIS account visited (newest first), classified again from the very
    screenshot and bio production used, through `classify_profile_niche`. The reference is the
    judge model answering the same production prompt; each arm is scored on agreement with it.
  - `post`: the posts THIS account commented on with AI. Each post is described again from its
    screenshot (`analyze_post`), then each description is handed to the comment writer
    (`generate_smart_comment`, in the account's own voice), because the writer never sees the
    image: a wrong description is a wrong comment, and the anchor check cannot catch it. A judge
    that DOES see the image grades every description and every comment, blind.

Arms (`ARMS`): the production models through OpenRouter (A0), then Claude through Anthropic, with
reasoning off or on. Reasoning is a bench-only switch of the transport (`reasoning_effort`). Any other
model joins as `<provider>:<model id>` (`openrouter:google/gemini-3.8-flash`); `--writer-arms ""` grades
the descriptions alone.

What the replay leaves out, and says so: the comment thread read on screen (not stored) and the
relevance decision (every arm writes a comment so that every arm can be judged).

Usage
-----
    # The sample only, no call:
    python scripts/eval/replay_by_account.py --accounts our_account_1,our_account_2 --profiles 2 --posts 2

    # The run. TAKTIK_DB_PATH must point at a COPY of the base: the run's rows are written there.
    python scripts/eval/replay_by_account.py --db <copy> --accounts ... --taxonomy niche_taxonomy.json \\
        --profiles 2 --posts 2 --run --budget 0.80

Keys: OPENROUTER_API_KEY for A0, ANTHROPIC_API_KEY for the Claude arms and the judge.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import random
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_models import (  # noqa: E402 — the bench's own tools, one copy of each
    BudgetExceeded,
    SpendCapture,
    append_jsonl,
    compare_classification,
    connect,
    load_persona,
    profile_context_of,
    service_on,
    unwrap,
)
from taktik.core.ai.credential import KEY_ENV, AICredential  # noqa: E402
from taktik.core.ai.factory import build_ai_service  # noqa: E402
from taktik.core.ai.openrouter_policy import PROVIDER_ANTHROPIC, PROVIDER_OPENROUTER  # noqa: E402
from taktik.core.ai.providers.anthropic import AnthropicTransport  # noqa: E402
from taktik.core.database.ai_benchmark import AIBenchmark  # noqa: E402

APP_DATA = Path(os.environ.get("APPDATA", "")) / "taktik-desktop"
LIVE_DB = APP_DATA / "taktik-data.db"
SCREENSHOTS = APP_DATA / "ai-screenshots"
JUDGE_MODEL = "claude-opus-5-5"
# A post screenshot is written by the app when the post is analysed, a few seconds before the
# comment goes out (30 s median on our accounts); one older than this belongs to another visit.
POST_SHOT_MAX_AGE_S = 1800


@dataclass(frozen=True)
class Arm:
    key: str
    label: str
    provider: str
    model: Optional[str]  # None: the policy's production model for the task
    reasoning: Optional[str] = None  # adaptive thinking at this effort; None: thinking off


ARMS: Dict[str, Arm] = {arm.key: arm for arm in (
    Arm("A0", "production (OpenRouter)", PROVIDER_OPENROUTER, None),
    Arm("A1", "Haiku 5.5", PROVIDER_ANTHROPIC, "claude-haiku-5-5"),
    Arm("A2", "Haiku 5.5, reasoning medium", PROVIDER_ANTHROPIC, "claude-haiku-5-5", "medium"),
    Arm("A3", "Sonnet 5.5", PROVIDER_ANTHROPIC, "claude-sonnet-5-5"),
    Arm("A4", "Sonnet 5.5, reasoning low", PROVIDER_ANTHROPIC, "claude-sonnet-5-5", "low"),
    Arm("A5", "Sonnet 5.5, reasoning medium", PROVIDER_ANTHROPIC, "claude-sonnet-5-5", "medium"),
)}
REFERENCE = Arm("REF", "Opus 5.5 (reference)", PROVIDER_ANTHROPIC, JUDGE_MODEL)


class TokenRecorder:
    """The service's transport, with each answer's tokens kept: the cost per call is measured,
    and the tokens tell where it went (input, cache, output, thinking)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.provider = inner.provider
        self.label = inner.label
        self.last: Dict[str, Any] = {}

    def complete(self, call: Any) -> Dict[str, Any]:
        answer = self.inner.complete(call)
        self.last = {"tokens": answer.get("tokens"), "usage": answer.get("usage"), "model": answer.get("model")}
        return answer


def credentials() -> Dict[str, AICredential]:
    return {provider: AICredential(provider=provider, api_key=os.environ.get(KEY_ENV[provider], "").strip())
            for provider in (PROVIDER_OPENROUTER, PROVIDER_ANTHROPIC)}


def service_for(arm: Arm, keys: Dict[str, AICredential], spend: SpendCapture,
                taxonomy: Optional[Dict[str, list]]) -> Any:
    """An AIService answering as `arm`: its provider, its model on every task, its reasoning."""
    credential = keys[arm.provider]
    if arm.model is None:
        service = build_ai_service(api_key=credential.api_key, provider=credential.provider, ipc=spend,
                                   niche_taxonomy=taxonomy)
    else:
        service = service_on(arm.model, credential, spend, taxonomy)
    if arm.reasoning:
        service.transport = AnthropicTransport(credential.api_key, reasoning_effort=arm.reasoning)
    service.transport = TokenRecorder(service.transport)
    return service


# ------------------------------------------------------------------------------- the samples


def account_ids(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    """The account row: `legacy_account_id` is the id the interactions and comments carry."""
    return conn.execute(
        "SELECT id, legacy_account_id, username FROM accounts WHERE lower(username) = lower(?) LIMIT 1",
        (username,),
    ).fetchone()


def sample_profiles(conn: sqlite3.Connection, legacy_id: int, count: int, seed: int) -> List[Dict[str, Any]]:
    """`count` profiles this account visited, picked at random among its 300 latest visits that
    have a classification and the screenshot it was made from."""
    visits = conn.execute(
        """SELECT target_username, max(interaction_time) AS seen FROM interactions
           WHERE account_id = ? AND target_username IS NOT NULL
           GROUP BY target_username ORDER BY seen DESC LIMIT 300""",
        (legacy_id,),
    ).fetchall()
    usernames = [row["target_username"] for row in visits]
    random.Random(seed).shuffle(usernames)
    picked: List[Dict[str, Any]] = []
    for username in usernames:
        shot = SCREENSHOTS / f"ai_{username}.jpg"
        if not shot.exists():
            continue
        row = conn.execute(
            """SELECT q.username, q.ai_classification, q.niche_slug, q.sub_niche_slug,
                      p.biography, p.business_category, p.website, p.followers_count,
                      p.following_count, p.posts_count, p.is_private, p.is_verified
               FROM profile_qualification q
               LEFT JOIN social_profiles p ON p.platform = 'instagram' AND p.username = q.username
               WHERE q.platform = 'instagram' AND q.username = ?
                 AND q.ai_classification IS NOT NULL AND q.ai_classification <> ''""",
            (username,),
        ).fetchone()
        if not row:
            continue
        # Some old rows hold a classification that is not JSON: no baseline to compare with, so
        # the profile is left out before anything is paid for it.
        try:
            json.loads(row["ai_classification"])
        except json.JSONDecodeError as exc:
            print(f"  @{username}: stored classification is not JSON ({exc}), left out of the sample")
            continue
        picked.append({"row": row, "shot": shot})
        if len(picked) >= count:
            break
    return picked


def post_shots() -> Dict[str, List[tuple]]:
    """Every post screenshot on disk, by author: (written at, path)."""
    shots: Dict[str, List[tuple]] = defaultdict(list)
    for path in SCREENSHOTS.glob("post_*.jpg"):
        match = re.match(r"post_(.+)_\d+\.jpg$", path.name)
        if match:
            shots[match.group(1).lower()].append((path.stat().st_mtime, path))
    return shots


def shot_before(shots: Dict[str, List[tuple]], author: str, posted_at: str) -> Optional[Path]:
    """The screenshot the app wrote for this post: the author's latest one before the comment."""
    moment = dt.datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    stamp = moment.timestamp()
    near = [(stamp - written, path) for written, path in shots.get(author.lower(), [])
            if -60 < stamp - written < POST_SHOT_MAX_AGE_S]
    return min(near)[1] if near else None


def sample_posts(conn: sqlite3.Connection, legacy_id: int, count: int, seed: int,
                 shots: Dict[str, List[tuple]]) -> List[Dict[str, Any]]:
    """`count` posts this account commented on with AI, each with its screenshot.

    Only comments written from a stored description: until September many went out with none
    (all of July, half of August), and grading those against a fresh description would measure
    the old defect, not the models."""
    rows = conn.execute(
        """SELECT id, coalesce(post_author, target_username) AS author, post_caption, post_description,
                  comment_text, ai_model, language, posted_at
           FROM posted_comments
           WHERE account_id = ? AND source = 'ai' AND kind = 'comment' AND platform = 'instagram'
             AND comment_text IS NOT NULL AND comment_text <> ''
             AND post_description IS NOT NULL AND post_description <> ''""",
        (legacy_id,),
    ).fetchall()
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    picked: List[Dict[str, Any]] = []
    for row in rows:
        shot = shot_before(shots, row["author"] or "", row["posted_at"])
        if shot:
            picked.append({"row": row, "shot": shot})
        if len(picked) >= count:
            break
    return picked


def recent_comments_before(conn: sqlite3.Connection, legacy_id: int, posted_at: str) -> List[str]:
    """What the account had published just before: the anti-tic guard's input, as it stood then
    (production reads the latest 12, `PostedCommentsRepository.recent_texts`)."""
    rows = conn.execute(
        """SELECT comment_text FROM posted_comments
           WHERE account_id = ? AND source = 'ai' AND posted_at < ? AND comment_text <> ''
           ORDER BY posted_at DESC LIMIT 12""",
        (legacy_id, posted_at),
    ).fetchall()
    return [row["comment_text"] for row in rows]


def target_gender(conn: sqlite3.Connection, username: str) -> str:
    row = conn.execute(
        "SELECT ai_gender FROM profile_qualification WHERE platform = 'instagram' AND username = ?",
        (username,),
    ).fetchone()
    return (row["ai_gender"] if row else "") or ""


# ------------------------------------------------------------------------------- the calls


def paid(spend: SpendCapture, budget: float, what: str) -> None:
    if spend.total_usd >= budget:
        raise BudgetExceeded(f"budget reached before {what}")


def measured(service: Any, spend: SpendCapture, before: float, started: float) -> Dict[str, Any]:
    recorder: TokenRecorder = service.transport
    return {"usd": round(spend.total_usd - before, 6), "seconds": round(time.time() - started, 2),
            "tokens": recorder.last.get("tokens"), "served_model": recorder.last.get("model")}


def classify(service: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    row = case["row"]
    try:
        answer = service.classify_profile_niche(
            username=row["username"], screenshot_path=str(case["shot"]),
            profile_context=profile_context_of(row), response_language="fr", platform="instagram",
        ) or {}
    except Exception as exc:  # noqa: BLE001 — one bad profile must not end the benchmark
        answer = {"error": str(exc)}
    return answer


def describe(service: Any, case: Dict[str, Any]) -> Dict[str, Any]:
    row = case["row"]
    try:
        return service.analyze_post(str(case["shot"]), username=row["author"], response_language="fr",
                                    post_caption=row["post_caption"] or "") or {}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


def write_comment(service: Any, case: Dict[str, Any], description: str, persona: Optional[Dict[str, Any]],
                  recent: List[str], gender: str) -> Dict[str, Any]:
    row = case["row"]
    try:
        return service.generate_smart_comment(
            post_description=description, username=row["author"] or "unknown",
            niche=(persona or {}).get("niche") or "general", language=row["language"] or "auto",
            post_caption=row["post_caption"] or "", account_persona=persona, platform="instagram",
            app_language="fr", recent_comments=recent, target_gender=gender,
        ) or {}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


JUDGE_SYSTEM = """You grade an Instagram growth tool, blind. You see a post (its screenshot and the author's caption), several DESCRIPTIONS of it written by different models, and several COMMENTS other models wrote to publish under it, in the voice of the account described below. The comment writers never saw the image: they only had the caption and one of the descriptions.

Grade each description:
- faithful: 2 = everything stated is visible or in the caption; 1 = a minor inaccuracy or a key element missed; 0 = states something false about the post (wrong subject, invented object, misread text)
- errors: the false or invented statements, quoted briefly (empty list if none)

Grade each comment:
- relevance: 3 = specific to THIS post and natural; 2 = relevant but could fit many similar posts; 1 = generic, could go under anything; 0 = off the mark (reacts to something the post does not show or say)
- invented: true if it asserts a fact about the post that is not in the image or caption
- language_ok: true if written in the language the post calls for, correctly
- spelling: number of spelling, grammar or agreement mistakes
- publishable: would a careful community manager publish it as is, for this account

Answer with JSON only:
{"descriptions": {"D1": {"faithful": 2, "errors": []}, ...}, "comments": {"C1": {"relevance": 3, "invented": false, "language_ok": true, "spelling": 0, "publishable": true, "why": "<8 words>"}, ...}}"""


def judge_post(judge: Any, case: Dict[str, Any], persona: Optional[Dict[str, Any]],
               descriptions: Dict[str, str], comments: Dict[str, str]) -> Dict[str, Any]:
    """One call per post: the judge sees the image and every candidate under a neutral label."""
    row = case["row"]
    image = base64.b64encode(case["shot"].read_bytes()).decode("ascii")
    voice = json.dumps({k: v for k, v in (persona or {}).items() if v}, ensure_ascii=False)
    text = (
        f"Account voice: {voice}\nAuthor: @{row['author']}\nCaption: {(row['post_caption'] or '(none)')[:800]}\n\n"
        + "DESCRIPTIONS\n" + "\n".join(f"{label}: {value}" for label, value in descriptions.items())
        + "\n\nCOMMENTS\n" + "\n".join(f"{label}: {value}" for label, value in comments.items())
    )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
            {"type": "text", "text": text},
        ]},
    ]
    answer = judge._call_model(JUDGE_MODEL, messages, max_tokens=4000, label=f"judge @{row['author']}",
                               kind="other")
    raw = (answer.get("text") or "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        return json.loads(match.group(0)) if match else {"error": "no JSON", "raw": raw[:500]}
    except json.JSONDecodeError as exc:
        return {"error": f"bad JSON: {exc}", "raw": raw[:500]}


# ------------------------------------------------------------------------------- the tasks


def run_profiles(account: str, cases: List[Dict[str, Any]], arms: List[Arm], services: Dict[str, Any],
                 spend: SpendCapture, budget: float, sink: Path, run_id: Optional[int]) -> None:
    for case in cases:
        username = case["row"]["username"]
        baseline = json.loads(case["row"]["ai_classification"] or "{}")
        answers: Dict[str, Dict[str, Any]] = {}
        for arm in [REFERENCE] + arms:
            paid(spend, budget, f"profile @{username} on {arm.key}")
            before, started = spend.total_usd, time.time()
            answer = classify(services[arm.key], case)
            answers[arm.key] = unwrap(answer)
            cost = measured(services[arm.key], spend, before, started)
            reference = answers[REFERENCE.key]
            record = {
                "task": "profile", "account": account, "case": username, "arm": arm.key, "label": arm.label,
                **cost, "error": answer.get("error"), "candidate": answers[arm.key],
                "vs_reference": compare_classification(reference, answers[arm.key]) if arm is not REFERENCE else None,
                "vs_stored": compare_classification(baseline, answers[arm.key]),
            }
            append_jsonl(sink, record)
            AIBenchmark.record(run_id=run_id, task="profile", case_ref=f"{account}/{username}", model=arm.label,
                               served_model=cost["served_model"], cost_usd=cost["usd"], seconds=cost["seconds"],
                               baseline=reference, candidate=answers[arm.key], agreement=record["vs_reference"])
            print(f"  profile {account} @{username} {arm.key} · ${spend.total_usd:.4f}", flush=True)


def run_posts(account: str, legacy_id: int, cases: List[Dict[str, Any]], conn: sqlite3.Connection,
              arms: List[Arm], writer_arms: List[Arm], services: Dict[str, Any], judge: Any,
              persona: Optional[Dict[str, Any]], spend: SpendCapture, budget: float, sink: Path,
              run_id: Optional[int]) -> None:
    for case in cases:
        row = case["row"]
        recent = recent_comments_before(conn, legacy_id, row["posted_at"])
        gender = target_gender(conn, row["author"] or "")
        # What actually went out, graded with the rest under the same blind labels.
        descriptions: Dict[str, str] = {"stored": row["post_description"] or ""}
        comments: Dict[str, str] = {"stored": row["comment_text"] or ""}
        records: Dict[str, Dict[str, Any]] = {}
        for arm in arms:
            paid(spend, budget, f"post {row['id']} description on {arm.key}")
            before, started = spend.total_usd, time.time()
            answer = describe(services[arm.key], case)
            descriptions[arm.key] = answer.get("description") or ""
            records[f"D:{arm.key}"] = {"step": "description", "arm": arm.key, "label": arm.label,
                                       **measured(services[arm.key], spend, before, started),
                                       "text": descriptions[arm.key], "error": answer.get("error")}
        for described_by in arms:
            if not descriptions[described_by.key]:
                continue
            for writer in writer_arms:
                paid(spend, budget, f"post {row['id']} comment {described_by.key}>{writer.key}")
                before, started = spend.total_usd, time.time()
                answer = write_comment(services[writer.key], case, descriptions[described_by.key],
                                       persona, recent, gender)
                key = f"{described_by.key}>{writer.key}"
                comments[key] = answer.get("comment") or ""
                records[f"C:{key}"] = {
                    "step": "comment", "described_by": described_by.key, "writer": writer.key,
                    **measured(services[writer.key], spend, before, started), "text": comments[key],
                    "anchor_ok": answer.get("anchor_ok"), "used_safe_comment": answer.get("used_safe_comment"),
                    "agreement_fixes": answer.get("agreement_fixes"), "error": answer.get("error"),
                }
        # Blind: neutral labels, shuffled, the key kept on our side only.
        order = random.Random(f"{row['id']}").sample
        d_keys = order(list(descriptions), len(descriptions))
        c_keys = order([k for k in comments if comments[k]], len([k for k in comments if comments[k]]))
        d_label = {key: f"D{i}" for i, key in enumerate(d_keys, start=1)}
        c_label = {key: f"C{i}" for i, key in enumerate(c_keys, start=1)}
        paid(spend, budget, f"post {row['id']} judge")
        before, started = spend.total_usd, time.time()
        verdict = judge_post(judge, case, persona, {d_label[k]: descriptions[k] for k in d_keys},
                             {c_label[k]: comments[k] for k in c_keys})
        judge_cost = measured(judge, spend, before, started)
        record = {
            "task": "post", "account": account, "case": row["id"], "author": row["author"],
            "shot": case["shot"].name, "caption": (row["post_caption"] or "")[:600],
            "stored_model": row["ai_model"], "steps": records, "labels": {"d": d_label, "c": c_label},
            "judge": verdict, "judge_cost": judge_cost,
        }
        append_jsonl(sink, record)
        for step_key, step in records.items():
            AIBenchmark.record(run_id=run_id, task="post_" + step["step"], case_ref=f"{account}/{row['id']}",
                               model=step_key, served_model=step.get("served_model"), cost_usd=step["usd"],
                               seconds=step["seconds"], baseline={"stored": row["comment_text"]},
                               candidate={"text": step["text"]}, agreement=None)
        print(f"  post {account} #{row['id']} @{row['author']} judged · ${spend.total_usd:.4f}", flush=True)


# ------------------------------------------------------------------------------- the run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, required=True, help="a COPY of taktik-data.db (read-only here)")
    parser.add_argument("--accounts", required=True, help="our operated accounts, comma-separated usernames")
    parser.add_argument("--profiles", type=int, default=0, help="profiles per account")
    parser.add_argument("--posts", type=int, default=0, help="commented posts per account")
    parser.add_argument("--profile-arms", default="A0,A1,A3", help="arms that classify")
    parser.add_argument("--post-arms", default="A0,A1,A3,A4", help="arms that describe the posts")
    parser.add_argument("--writer-arms", default="A0,A3", help="arms that write the comments")
    parser.add_argument("--taxonomy", type=Path, help="the app's niche taxonomy JSON")
    parser.add_argument("--out", type=Path, default=Path("eval-out/by-account"))
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--note", default="")
    parser.add_argument("--budget", type=float, default=0.80, help="hard ceiling in USD")
    parser.add_argument("--run", action="store_true", help="actually call the models")
    args = parser.parse_args()

    def arms_of(spec: str) -> List[Arm]:
        arms: List[Arm] = []
        for key in (part.strip() for part in spec.split(",")):
            if not key:
                continue
            if key in ARMS:
                arms.append(ARMS[key])
                continue
            # Any other model, by its provider's id: `openrouter:google/gemini-3.8-flash`.
            provider, _, model = key.partition(":")
            if provider not in (PROVIDER_OPENROUTER, PROVIDER_ANTHROPIC) or not model:
                raise SystemExit(f"unknown arm {key!r}: A0..A5, or <provider>:<model>")
            arms.append(Arm(model, model, provider, model))
        return arms

    profile_arms, post_arms, writer_arms = arms_of(args.profile_arms), arms_of(args.post_arms), arms_of(args.writer_arms)
    if args.db.resolve() == LIVE_DB.resolve():
        print("Refusing the live base: give a copy.")
        return 1

    conn = connect(args.db)
    shots = post_shots() if args.posts else {}
    plan = []
    for username in [u.strip() for u in args.accounts.split(",") if u.strip()]:
        account = account_ids(conn, username)
        if not account:
            print(f"@{username}: not in accounts, skipped")
            continue
        legacy_id = account["legacy_account_id"]
        profiles = sample_profiles(conn, legacy_id, args.profiles, args.seed) if args.profiles else []
        posts = sample_posts(conn, legacy_id, args.posts, args.seed, shots) if args.posts else []
        persona = load_persona(conn, username)
        plan.append({"account": username, "legacy_id": legacy_id, "profiles": profiles, "posts": posts,
                     "persona": persona})
        print(f"@{username}: {len(profiles)} profiles, {len(posts)} posts, persona {'yes' if persona else 'NO'}")

    if not args.run:
        print("\nSample only — nothing called. Add --run --budget <dollars>.")
        return 0

    target = os.environ.get("TAKTIK_DB_PATH", "")
    if not target or Path(target).resolve() == LIVE_DB.resolve():
        print("TAKTIK_DB_PATH must point at the COPY: the run writes its rows there, never in the live base.")
        return 1
    keys = credentials()
    needed = {arm.provider for arm in profile_arms + post_arms + writer_arms} | {PROVIDER_ANTHROPIC}
    missing = [KEY_ENV[p] for p in needed if len(keys[p].api_key) < 10]
    if missing:
        print(f"Missing keys: {', '.join(missing)} — refusing to run.")
        return 1

    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8")) if args.taxonomy else None
    spend = SpendCapture()
    services = {arm.key: service_for(arm, keys, spend, taxonomy)
                for arm in {*profile_arms, *post_arms, *writer_arms, REFERENCE}}
    judge = services[REFERENCE.key]

    args.out.mkdir(parents=True, exist_ok=True)
    sink = args.out / "results.jsonl"
    if sink.exists():
        sink.unlink()
    run_id = AIBenchmark.start_run(
        seed=args.seed, sample_size=sum(len(p["profiles"]) + len(p["posts"]) for p in plan), budget_usd=args.budget,
        config={"bench": "by-account", "accounts": [p["account"] for p in plan],
                "profile_arms": [a.key for a in profile_arms], "post_arms": [a.key for a in post_arms],
                "writer_arms": [a.key for a in writer_arms], "judge": JUDGE_MODEL,
                "arms": {k: a.label for k, a in ARMS.items()}},
        note=args.note or None,
    )
    stopped = None
    try:
        for item in plan:
            run_profiles(item["account"], item["profiles"], profile_arms, services, spend, args.budget, sink, run_id)
            run_posts(item["account"], item["legacy_id"], item["posts"], conn, post_arms, writer_arms, services,
                      judge, item["persona"], spend, args.budget, sink, run_id)
    except BudgetExceeded as exc:
        stopped = str(exc)
        print(f"\nSTOPPED: {exc}")
    except KeyboardInterrupt:
        stopped = "interrupted by the operator"
    finally:
        AIBenchmark.finish_run(run_id=run_id, status="stopped" if stopped else "completed",
                               total_cost_usd=spend.total_usd)
        conn.close()

    print(f"\nSpent ${spend.total_usd:.4f} over {spend.calls} calls "
          f"({', '.join(f'{k} ${v:.4f}' for k, v in sorted(spend.by_kind.items()))}) · run #{run_id}")
    print(f"Results: {sink}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
