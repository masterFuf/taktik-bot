"""One launcher per workflow: the checks behind rule 1 of the anti-drift doctrine.

The manifest is the only list of workflows. Each declared workflow has ONE launcher: the
Agent handler registered under its id, which wraps a `run_*` function in the same
`agent_handler.py`. The bridge (desktop) and the CLI both call that launcher; what differs
between them is injected. On the app side, each workflow bridge is spawned by ONE Electron
module, which pages, the scheduler and the Agent all reach through its IPC.

Red when:
- a handler is registered under an id the manifest does not declare;
- a runnable workflow of the manifest has no registered launcher;
- an entry point (a bridge, the CLI, the Lab's whole-workflow runner) builds or calls a
  workflow engine itself instead of going through the launcher;
- a workflow bridge never reaches a launcher;
- a workflow bridge is spawned by more than one Electron module, or the spawn bypasses
  `BridgeProcessRunner`;
- the scheduler accepts a TikTok workflow type the manifest does not declare;
- an exception below no longer matches anything (the list only shrinks).

Lab actions (`*/diagnostics/actions/**`) are out of scope on purpose: AGENTS.md makes them
build the production workflow on the warm device to call ONE atomic step, not to run it.

Called by `audit_workflow_registry.py`, which is the gate; `--self-test` there proves each
rule still turns red on a fake second launcher.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

CORE = Path(__file__).resolve().parents[1]
ROOT = CORE.parent
APP = ROOT / "app"

MANIFEST_PATH = CORE / "workflows.manifest.json"
BRIDGES_MANIFEST_PATH = CORE / "bridges" / "bridges.manifest.json"
ELECTRON_DIR = APP / "electron"
SCHEDULER_TIKTOK_TYPES_PATH = APP / "src" / "app" / "hooks" / "scheduler" / "tiktok-workflow-types.ts"
BRIDGE_RUNNER = "electron/services/shared/bridge/process/BridgeProcessRunner.ts"
BRIDGE_PATHS = "electron/utils/paths.ts"

#: Families a bridge serves that are not workflows (diagnostics, schema).
NON_WORKFLOW_BRIDGE_GROUPS = {"compat", "database"}
#: Parameter / helper names through which a launcher receives its engine.
ENGINE_SLOTS = ("workflow_factory",)
ENGINE_SLOT_SUFFIX = "_runner"

# Every exception says why it holds and what removes it.
EXCEPTIONS: dict[str, dict[tuple[str, ...], str]] = {
    "manifest_without_launcher": {
        ("instagram.account.change_language",):
            "account family not unified yet (Q3): the bridge runs it, no handler.",
        ("tiktok.account.change_language",):
            "same as Instagram: the account bridge runs it, no handler yet.",
        ("instagram.engagement.notifications",):
            "notifications family (Q5) is being moved to a launcher in its own lot.",
        ("instagram.engagement.smart_comment",):
            "declared for the panel, runs inside the automation launcher; no own entry.",
    },
    "entry_point_engine": {
        # Instagram account (Q3): the bridge and the CLI build the workflows themselves.
        ("bridges/instagram/account/runtime/login.py", "LoginWorkflow"):
            "Q3, account lot: bridge builds LoginWorkflow, handler has its own copy.",
        ("bridges/instagram/account/runtime/logout.py", "LogoutWorkflow"):
            "Q3, account lot.",
        ("bridges/instagram/account/runtime/register.py", "SignupWorkflow"):
            "Q3, account lot.",
        ("bridges/instagram/account/runtime/language.py", "ChangeLanguageWorkflow"):
            "Q3, account lot (change_language has no handler yet).",
        ("bridges/instagram/account/runtime/switch.py", "SwitchAccountWorkflow"):
            "Q3, account lot: switch/list accounts are not in the manifest yet.",
        ("taktik/cli/commands/management_cmds.py", "LoginWorkflow"):
            "Q3, account lot: `auth login` bypasses the handler (no clean restart).",
        ("taktik/cli/main.py", "LoginWorkflow"):
            "Q3, account lot: CLI menu login bypasses the handler.",
        # Instagram notifications (Q5, handled in its own lot).
        ("bridges/instagram/engagement/runtime/notifications/bridge.py", "NotificationsEngagementWorkflow"):
            "Q5, notifications lot in progress.",
        # Instagram publication (Q4, postponed): no manifest id, three hosts build the engine.
        ("bridges/instagram/publish/runtime/bridge.py", "InstagramPostWorkflow"):
            "Q4 postponed: publication has no manifest id nor launcher.",
        ("taktik/cli/commands/publish_cmds.py", "InstagramPostWorkflow"):
            "Q4 postponed: CLI `publish` builds the engine itself.",
        ("bridges/compat/diagnostics/runtime/workflow_test/platforms/instagram/workflows/publish.py",
         "InstagramPostWorkflow"):
            "Q4 postponed: the Lab publish run builds the engine itself.",
        # Lab whole-run of Instagram automation: instrumented engine, not the launcher.
        ("bridges/compat/diagnostics/runtime/workflow_test/execution/lifecycle.py", "InstagramAutomation"):
            "Lab automation run instruments the engine; launcher needs a step hook first.",
        # CLI-only workflows the manifest does not declare: declare them or drop them.
        ("taktik/cli/main.py", "DMAutoReplyWorkflow"):
            "CLI-only DM auto-reply, no manifest id; decision pending (autoresponse mode).",
        ("taktik/cli/main.py", "PostScrapingWorkflow"):
            "CLI-only full post scraping, no manifest id; decision pending.",
        # TikTok account: handler exists, bridge still builds the workflows.
        ("bridges/tiktok/account/runtime/account_login.py", "TikTokLoginWorkflow"):
            "TikTok account lot: bridge not moved to the handler yet.",
        ("bridges/tiktok/account/runtime/account_logout.py", "TikTokLogoutWorkflow"):
            "TikTok account lot.",
        ("bridges/tiktok/account/runtime/account_register.py", "TikTokSignupWorkflow"):
            "TikTok account lot.",
        ("bridges/tiktok/account/runtime/account_language.py", "TikTokChangeLanguageWorkflow"):
            "TikTok account lot (change_language has no handler yet).",
        # Threads: handler exists, the bridge keeps its own config and calls the engine.
        ("bridges/threads/workflows/runtime/feed.py", "run_feed_and_interact"):
            "Threads lot: bridge builds its own config and calls the engine.",
        ("bridges/threads/workflows/runtime/search.py", "run_search_and_interact"):
            "Threads lot.",
    },
    "bridge_without_launcher": {
        ("account_bridge",): "Q3, account lot.",
        ("notifications_bridge",): "Q5, notifications lot in progress.",
        ("persona_analysis_bridge",):
            "persona analysis: no manifest id, no CLI; left as is by decision (Q6).",
        ("publish_bridge",): "Q4 postponed.",
        ("tiktok_account_bridge",): "TikTok account lot.",
        ("threads_bridge",): "Threads lot.",
    },
    "app_extra_launch_module": {
        ("desktop_bridge", "electron/services/tools/debug/bridge/DesktopDebugBridgeService.ts"):
            "`--debug` screen capture of the desktop bridge, a diagnostic, not a run.",
    },
}


@dataclass
class Report:
    """Findings of one check plus the exception keys it consumed."""

    findings: list[str] = field(default_factory=list)
    used: set[tuple[str, tuple[str, ...]]] = field(default_factory=set)

    def excuse(self, kind: str, key: tuple[str, ...], exceptions: Mapping) -> bool:
        if key in exceptions.get(kind, {}):
            self.used.add((kind, key))
            return True
        return False

    def extend(self, other: "Report") -> None:
        self.findings += other.findings
        self.used |= other.used


# --------------------------------------------------------------------------- manifest


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def runnable_ids(manifest: dict) -> set[str]:
    """Declared ids of the families that run something (not `ui` nor `planned`)."""
    from inventory_capabilities import kind_of, platform_families

    return {
        f"{platform}.{family}.{workflow}"
        for platform, family, workflows in platform_families(manifest)
        for workflow in workflows
        if kind_of(manifest, platform, family, workflow) not in ("ui", "planned")
    }


def registered_ids() -> list[str]:
    from audit_cli_coverage import build_full_registry, registered_ids as ids

    registry, failures = build_full_registry()
    if failures:
        raise RuntimeError(f"registrars failed to load: {failures}")
    return ids(registry)


def registrars() -> list[tuple[str, str]]:
    """(launcher module, registrar function), as the CLI registry assembles them."""
    sys.path.insert(0, str(CORE))
    from taktik.cli.common.registry_builder import REGISTRARS

    return sorted({(module, func) for _label, module, func in REGISTRARS})


def check_registry(declared: set[str], registered: Iterable[str], exceptions: Mapping) -> Report:
    report = Report()
    registered = set(registered)
    for workflow_id in sorted(registered - declared):
        report.findings.append(f"launched without being in the manifest: handler `{workflow_id}`")
    for workflow_id in sorted(declared - registered):
        if not report.excuse("manifest_without_launcher", (workflow_id,), exceptions):
            report.findings.append(f"manifest workflow without a launcher: `{workflow_id}`")
    return report


# --------------------------------------------------------------------------- bot sources


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def module_path(module: str) -> Path | None:
    base = CORE / Path(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _last_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def is_workflow_class(name: str) -> bool:
    return name.endswith("Workflow") and name[:1].isupper()


def _is_engine_slot(name: str) -> bool:
    return name in ENGINE_SLOTS or name.endswith(ENGINE_SLOT_SUFFIX)


def launcher_functions(trees: Iterable[ast.Module]) -> set[str]:
    """The `run_*` functions launcher modules define: the entry every host must call."""
    return {
        node.name
        for tree in trees
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("run_")
    }


def engine_names(trees: Iterable[ast.Module], launchers: set[str]) -> set[str]:
    """What launchers run: engine slot defaults, `slot or X`, `_default_workflow_factory`
    returns, and the `*Workflow` / `run_*` names they import from the core."""
    engines: set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                positional = args.posonlyargs + args.args
                pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
                pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
                for arg, default in pairs:
                    if _is_engine_slot(arg.arg) and _last_name(default):
                        engines.add(_last_name(default))
                if node.name == "_default_workflow_factory":
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.Return) and inner.value is not None and _last_name(inner.value):
                            engines.add(_last_name(inner.value))
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2:
                left, right = node.values
                if isinstance(left, ast.Name) and _is_engine_slot(left.id) and _last_name(right):
                    engines.add(_last_name(right))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("taktik."):
                engines |= {alias.asname or alias.name for alias in node.names if is_workflow_class(alias.name)}
        called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        # A `run_*` function the launcher imports AND calls is the engine it wraps.
        engines |= {name for name in _core_bindings(tree) & called if name.startswith("run_")}
    return {name for name in engines if name not in launchers}


def entry_point_files() -> list[Path]:
    """Bridges and CLI modules; the Lab's whole-workflow runner, not its atomic actions."""
    files: list[Path] = []
    for path in sorted((CORE / "bridges").rglob("*.py")):
        rel = path.relative_to(CORE).as_posix()
        if "__pycache__" in rel:
            continue
        if "/diagnostics/" in rel and "/diagnostics/runtime/workflow_test/" not in rel:
            continue
        files.append(path)
    files += [p for p in sorted((CORE / "taktik" / "cli").rglob("*.py")) if "__pycache__" not in p.parts]
    return files


def _core_bindings(tree: ast.Module) -> set[str]:
    """Names bound, anywhere in the module, by an import from the core."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("taktik"):
            bound |= {alias.asname or alias.name for alias in node.names}
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("taktik"):
                    bound.add(alias.asname or alias.name.split(".")[0])
    return bound


def engine_calls(tree: ast.Module, engines: set[str], launchers: set[str]) -> list[tuple[str, int]]:
    """Calls, in an entry point, to a core engine instead of its launcher."""
    bound = _core_bindings(tree)
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in bound:
            name = func.id
        elif isinstance(func, ast.Attribute):
            root = func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if not (isinstance(root, ast.Name) and root.id in bound):
                continue
            name = func.attr
        else:
            continue
        if name in launchers:
            continue
        if is_workflow_class(name) or name in engines:
            hits.append((name, node.lineno))
    return hits


def check_entry_points(sources: Mapping[str, ast.Module], engines: set[str], launchers: set[str],
                       exceptions: Mapping) -> Report:
    report = Report()
    for rel, tree in sorted(sources.items()):
        for name, line in sorted(set(engine_calls(tree, engines, launchers)), key=lambda h: h[1]):
            if report.excuse("entry_point_engine", (rel, name), exceptions):
                continue
            report.findings.append(
                f"second launcher: {rel}:{line} runs `{name}` itself instead of its launcher"
            )
    return report


# --------------------------------------------------------------------------- bridges


def workflow_bridges(bridges_manifest: dict) -> dict[str, str]:
    """Bridge name -> entry module, for the bridges that run workflows."""
    bridges: dict[str, str] = {}
    for group, entries in bridges_manifest.items():
        if group in NON_WORKFLOW_BRIDGE_GROUPS or not isinstance(entries, dict):
            continue
        for name, module in entries.items():
            if ".diagnostics." not in module:
                bridges[name] = module
    return bridges


def _imported_modules(tree: ast.Module, module: str, is_package: bool) -> set[str]:
    package = module if is_package else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            found.add(target)
            found |= {f"{target}.{alias.name}" for alias in node.names}
    return found


def _default_read(module: str):
    return module_path(module), None


def calls_entry(tree: ast.Module, entries: set[str]) -> bool:
    """Whether the module calls a launcher, a registrar or the CLI registry, from the core."""
    bound = _core_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in entries and node.func.id in bound:
                return True
    return False


def reaches_launcher(entry: str, entries: set[str], read=_default_read) -> bool:
    """Whether the bridge's own modules (`bridges.*`) call a launcher of the manifest."""
    seen: set[str] = set()
    todo = [entry]
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        path, tree = read(module)
        if path is None and tree is None:
            continue
        tree = tree or parse(path)
        is_package = path is not None and path.name == "__init__.py"
        if calls_entry(tree, entries):
            return True
        imported = _imported_modules(tree, module, is_package)
        todo += [m for m in imported if m.startswith("bridges.") and m not in seen]
    return False


def check_bridges(bridges: Mapping[str, str], entries: set[str], exceptions: Mapping,
                  read=None) -> Report:
    report = Report()
    for name, module in sorted(bridges.items()):
        if reaches_launcher(module, entries, read or _default_read):
            continue
        if not report.excuse("bridge_without_launcher", (name,), exceptions):
            report.findings.append(f"bridge `{name}` ({module}) reaches no launcher of the manifest")
    return report


# --------------------------------------------------------------------------- app

SPAWN_LITERAL_RE = re.compile(r"spawnBridgeProcess\(\s*'([a-z0-9_]+)'")
BRIDGE_NAME_RE = re.compile(r"\bbridgeName:\s*'([a-z0-9_]+)'")
RUN_OPTIONS_RE = re.compile(r"\bbridge:\s*'([a-z0-9_]+)'")
RAW_SPAWN_RE = re.compile(r"\b(getSpawnArgs|getBridgeCommand)\(|'launcher\.py'")


def _enclosing_object(text: str, pos: int) -> str:
    depth = 0
    start = -1
    for i in range(pos - 1, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start < 0:
        return ""
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return text[start:]


def electron_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in sorted(ELECTRON_DIR.rglob("*.ts")):
        rel = path.relative_to(APP).as_posix()
        if "__tests__" in rel or rel.endswith((".test.ts", ".d.ts")):
            continue
        sources[rel] = path.read_text(encoding="utf-8-sig")
    return sources


def launch_modules(sources: Mapping[str, str], bridges: Iterable[str]) -> dict[str, set[str]]:
    """Bridge -> Electron modules that name it as the process to spawn.

    A spawn target is the first argument of `spawnBridgeProcess`, the `bridgeName` of a
    launch request, or the `bridge` of a run-options object (one that carries `processKey`).
    A crash report or a stream label names the bridge too, and is not a launch.
    """
    wanted = set(bridges)
    found: dict[str, set[str]] = {name: set() for name in wanted}
    for rel, text in sources.items():
        names = set(SPAWN_LITERAL_RE.findall(text)) | set(BRIDGE_NAME_RE.findall(text))
        for match in RUN_OPTIONS_RE.finditer(text):
            if "processKey" in _enclosing_object(text, match.start()):
                names.add(match.group(1))
        for name in names & wanted:
            found[name].add(rel)
    return found


def check_app(sources: Mapping[str, str], bridges: Iterable[str], exceptions: Mapping) -> Report:
    report = Report()
    for rel, text in sorted(sources.items()):
        if rel in (BRIDGE_RUNNER, BRIDGE_PATHS):
            continue
        if RAW_SPAWN_RE.search(text):
            report.findings.append(f"app spawns a bridge outside BridgeProcessRunner: {rel}")
    for bridge, modules in sorted(launch_modules(sources, bridges).items()):
        kept = {m for m in modules if not report.excuse("app_extra_launch_module", (bridge, m), exceptions)}
        if len(kept) > 1:
            report.findings.append(
                f"second launch service: `{bridge}` is spawned by {len(kept)} modules: {sorted(kept)}"
            )
        elif not kept:
            report.findings.append(f"no launch service found for `{bridge}` (spawn shape changed?)")
    return report


TS_ARRAY_RE = re.compile(r"export const (?P<name>[A-Z0-9_]+) = \[(?P<body>.*?)\] as const", re.S)


def scheduler_tiktok_types(text: str) -> list[str]:
    for match in TS_ARRAY_RE.finditer(text):
        if match.group("name") == "TIKTOK_AUTOMATION_WORKFLOW_TYPES":
            return re.findall(r"'([^']+)'", match.group("body"))
    return []


def check_scheduler(manifest: dict, text: str) -> Report:
    report = Report()
    types = scheduler_tiktok_types(text)
    if not types:
        report.findings.append("scheduler TIKTOK_AUTOMATION_WORKFLOW_TYPES not found")
    declared = set(manifest.get("tiktok", {}).get("automation", []))
    for workflow_type in types:
        if workflow_type not in declared:
            report.findings.append(
                f"scheduler launches TikTok `{workflow_type}`, absent from manifest tiktok.automation"
            )
    return report


# --------------------------------------------------------------------------- run


@dataclass
class Inputs:
    manifest: dict
    registered: list[str]
    registrar_funcs: list[str]
    launcher_trees: list[ast.Module]
    entry_sources: dict[str, ast.Module]
    bridges: dict[str, str]
    electron: dict[str, str] | None
    scheduler_text: str | None
    bridge_reader: object = None


def collect_inputs() -> Inputs:
    pairs = registrars()
    mods = sorted({module for module, _func in pairs})
    has_app = ELECTRON_DIR.is_dir()
    return Inputs(
        manifest=load_json(MANIFEST_PATH),
        registered=registered_ids(),
        registrar_funcs=sorted({func for _module, func in pairs}),
        launcher_trees=[parse(module_path(m)) for m in mods],
        entry_sources={p.relative_to(CORE).as_posix(): parse(p) for p in entry_point_files()},
        bridges=workflow_bridges(load_json(BRIDGES_MANIFEST_PATH)),
        electron=electron_sources() if has_app else None,
        scheduler_text=SCHEDULER_TIKTOK_TYPES_PATH.read_text(encoding="utf-8-sig") if has_app else None,
    )


def run_checks(inputs: Inputs, exceptions: Mapping = EXCEPTIONS) -> list[str]:
    launchers = launcher_functions(inputs.launcher_trees)
    engines = engine_names(inputs.launcher_trees, launchers)
    report = Report()
    report.extend(check_registry(runnable_ids(inputs.manifest), inputs.registered, exceptions))
    report.extend(check_entry_points(inputs.entry_sources, engines, launchers, exceptions))
    entries = launchers | set(inputs.registrar_funcs) | {"build_registry"}
    report.extend(check_bridges(inputs.bridges, entries, exceptions, inputs.bridge_reader))
    if inputs.electron is not None:
        report.extend(check_app(inputs.electron, inputs.bridges, exceptions))
    if inputs.scheduler_text is not None:
        report.extend(check_scheduler(inputs.manifest, inputs.scheduler_text))
    for kind, entries in exceptions.items():
        for key in entries:
            if (kind, key) not in report.used:
                report.findings.append(f"stale exception, remove it: {kind} {key}")
    return report.findings


# --------------------------------------------------------------------------- self-test

FAKE_BRIDGE_ENGINE = (
    "from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow\n"
    "ForYouWorkflow(None, {}).run()\n"
)
FAKE_CLI_ENGINE = (
    "from taktik.core.social_media.threads.workflows import run_feed_and_interact\n"
    "run_feed_and_interact({})\n"
)


def _variant(inputs: Inputs, **changes) -> Inputs:
    fields = dict(inputs.__dict__)
    fields.update(changes)
    return Inputs(**fields)


def self_test_cases(inputs: Inputs) -> dict[str, tuple[Inputs, dict, str]]:
    """Each fake second launcher, and the words its finding must carry."""
    manifest = json.loads(json.dumps(inputs.manifest))
    manifest["tiktok"]["automation"].append("fake_declared")
    stale = {kind: dict(entries) for kind, entries in EXCEPTIONS.items()}
    stale["bridge_without_launcher"][("fake_bridge_gone",)] = "fake."
    fake_tree = ast.parse("from bridges.common.runtime.ipc import send_error\nsend_error('x')\n")
    reader = lambda module: (None, fake_tree) if module == "bridges.fake.entry" else _default_read(module)  # noqa: E731
    electron = inputs.electron or {}
    cases = {
        "bridge builds an engine": (_variant(inputs, entry_sources={
            **inputs.entry_sources, "bridges/tiktok/fake/second.py": ast.parse(FAKE_BRIDGE_ENGINE)}),
            EXCEPTIONS, "second launcher: bridges/tiktok/fake/second.py"),
        "CLI calls an engine function": (_variant(inputs, entry_sources={
            **inputs.entry_sources, "taktik/cli/commands/fake_second.py": ast.parse(FAKE_CLI_ENGINE)}),
            EXCEPTIONS, "second launcher: taktik/cli/commands/fake_second.py"),
        "handler outside the manifest": (_variant(inputs, registered=[
            *inputs.registered, "instagram.automation.fake_unlisted"]),
            EXCEPTIONS, "launched without being in the manifest"),
        "manifest id without launcher": (_variant(inputs, manifest=manifest),
            EXCEPTIONS, "without a launcher: `tiktok.automation.fake_declared`"),
        "bridge reaches no launcher": (_variant(inputs, bridges={
            **inputs.bridges, "fake_bridge": "bridges.fake.entry"}, bridge_reader=reader),
            EXCEPTIONS, "bridge `fake_bridge`"),
        "stale exception": (inputs, stale, "stale exception"),
    }
    if inputs.electron is not None:
        cases["second launch service"] = (_variant(inputs, electron={
            **electron, "electron/services/fake/SchedulerLauncher.ts":
                "spawnBridgeProcess('tiktok_bridge', [configPath])\n"}),
            EXCEPTIONS, "second launch service: `tiktok_bridge`")
        cases["spawn outside the runner"] = (_variant(inputs, electron={
            **electron, "electron/services/fake/RawSpawn.ts":
                "const a = getSpawnArgs('tiktok_bridge', [])\n"}),
            EXCEPTIONS, "outside BridgeProcessRunner")
        cases["scheduler type outside the manifest"] = (_variant(inputs, scheduler_text=(
            (inputs.scheduler_text or "").replace("'for_you',", "'for_you',\n  'fake_type',", 1))),
            EXCEPTIONS, "`fake_type`")
    return cases


def self_test(inputs: Inputs) -> list[str]:
    """Names of the cases the checks failed to turn red on."""
    baseline = set(run_checks(inputs))
    missed = []
    for name, (variant, exceptions, expected) in self_test_cases(inputs).items():
        new = [f for f in run_checks(variant, exceptions) if f not in baseline]
        if not any(expected in finding for finding in new):
            missed.append(name)
    return missed


__all__ = ["EXCEPTIONS", "Inputs", "collect_inputs", "run_checks", "self_test", "self_test_cases"]
