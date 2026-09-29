"""Layout of the engine's tree: a folder of the table holds only what the table lets it hold.

`LAYOUT` is the table of contents of the tree, written once: for a folder, the sub-folders and the files it
may hold directly, with its owner. A framework fixes its folders (`src/Controller`, `src/Command`...) so that
everyone knows where to look before opening a file; the table does the same and this gate keeps the tree to
it (AGENTS.md, section Structure). A new folder is documented in AGENTS.md first, then added here.

How to read an entry (`Folder`):

- a name listed in `folders` or `files` must be there, and what is not listed may not be there;
- a pattern widens what may be there and requires nothing: `ANY_FOLDER` (any sub-folder), `ANY_PYTHON` (any
  `.py` file), `PLATFORM` (a platform), `ENTRY` (a bridge entry of `bridges/bridges.manifest.json` that lives
  in this folder, `<key>.py`; at least one must be there);
- `vocabulary=True`: the listed names are a vocabulary, any of them may be there and none is required (not
  every platform has every kind of bridge);
- `never_below`: a folder name that may appear nowhere under the folder (no `runtime/` under `bridges/`).

A key may hold `PLATFORM` (`bridges/<platform>`: the folder of each platform) or `*` (`bridges/<platform>/*`:
each folder its parent allows); the most precise key wins (`bridges/tiktok/automation` over
`bridges/<platform>/*`). The platforms are the folders of `taktik/core/social_media/`, read from the tree: the
one list of the platforms, never written by hand. The families of `taktik/core` stay listed once, in
`CORE_FAMILIES` of `audit_import_layers.py`, and that gate refuses a folder of `taktik/core` that is not a
family: the table does not repeat that rule (it has no entry for `taktik/core`).

The manifest of the bridges is read too: each value is `bridges.<platform>.<bridge folder>.<key>` or
`bridges.tools.<tool>.<key>` and its file exists, and in the folder of a bridge only its entry is named
`*_bridge.py`.

The files are the ones git has or would add: tracked, or untracked and not ignored (`git ls-files --cached
--others --exclude-standard`), still on disk. A script forgotten at the root of `scripts/` is seen before its
first commit, as a stray file of a working copy is (the private `audit_sqlite_schema_docs.py`, until it is
filed where `.gitignore` expects it); what git ignores is not part of the tree: the `__pycache__` folders
(`.gitignore`), a folder left with its caches only (`taktik/config/` in an old checkout), the build output.

The table today: `scripts/` filed by usage (tree lot 2), `taktik/` and its CLI (tree lot 3), the folder of the
platforms (tree lot 4), `bridges/` with its tools and the Cartography Lab (tree lot 5; the Lab layout gate of
the old tree, `audit_diagnostics_runtime_layout.py`, is folded in here), `bridges/common/` flat (tree lot 6: the
device primitives went to the core).

The gate is red when:

- a folder of the table holds a sub-folder or a file it does not let in (a `.py` at the root of `scripts/`:
  file it in its usage folder);
- an entry of the table no longer exists (a listed sub-folder without a file, a listed file gone): the table
  says what is there, drop the entry;
- git ignores a listed sub-folder: a file added there would vanish from `git status` (the unanchored `build/`
  of the `.gitignore` did it to `scripts/build/`);
- a folder named in `never_below` appears under its folder;
- a value of the bridges manifest is out of its place or its file is gone, or a `*_bridge.py` in the folder of a
  bridge is no entry.

    python scripts/audits/audit_tree_layout.py              # green / red
    python scripts/audits/audit_tree_layout.py --self-test  # each kind of misplaced entry turns it red
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

CORE = Path(__file__).resolve().parents[2]
MANIFEST = "bridges/bridges.manifest.json"
PLATFORMS_FOLDER = "taktik/core/social_media"

PLATFORM = "<platform>"
ANY_FOLDER = "*"
ANY_PYTHON = "*.py"
ENTRY = "<entry>"
PATTERNS = frozenset({PLATFORM, ANY_FOLDER, ANY_PYTHON, ENTRY})


@dataclass(frozen=True)
class Folder:
    """What a folder of the tree holds directly, and who owns it."""

    folders: frozenset[str]
    files: frozenset[str]
    owner: str
    vocabulary: bool = False
    never_below: frozenset[str] = frozenset()


def lab_modules(*names: str) -> frozenset[str]:
    """A folder of the Lab: any Python file, and these modules at least."""
    return frozenset({ANY_PYTHON, *names})


LAYOUT: dict[str, Folder] = {
    "scripts": Folder(
        folders=frozenset({"audits", "build", "dev", "eval", "generate", "hooks", "lab", "repairs"}),
        files=frozenset({"install.ps1", "install.sh"}),
        owner="the tooling, filed by usage; at the root, the public install commands only",
    ),
    "taktik": Folder(
        folders=frozenset({"cli", "core"}),
        files=frozenset({"__init__.py", "__main__.py"}),
        owner="the package: its CLI and the engine (the families of `core/` are checked by audit_import_layers.py)",
    ),
    "taktik/cli": Folder(
        folders=frozenset({"commands", "menus", "hosts", "support", "locales"}),
        files=frozenset({"__init__.py", "main.py"}),
        owner="the CLI, the other host of the engine; `main.py` holds the click root and the entry points of setup.py",
    ),
    "taktik/cli/commands": Folder(
        folders=frozenset({PLATFORM}),
        files=frozenset({ANY_PYTHON}),
        owner="one file per click group; what belongs to one platform goes in the folder of that platform",
    ),
    "taktik/cli/commands/<platform>": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON}), owner="the commands of one platform",
    ),
    "taktik/cli/menus": Folder(folders=frozenset(), files=frozenset({ANY_PYTHON}), owner="the interactive menus"),
    "taktik/cli/hosts": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON}),
        owner="the sessions the CLI opens on a phone, and the registry of its workflows",
    ),
    "taktik/cli/support": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON}),
        owner="what the commands and the menus share: language, banner, base, device choice, version",
    ),
    "taktik/cli/locales": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON}), owner="the texts of the CLI, one file per language",
    ),
    PLATFORMS_FOLDER: Folder(
        folders=frozenset({PLATFORM}),
        files=frozenset({"__init__.py"}),
        owner="the platforms, one folder each: the one list of the platforms that every rule reads",
    ),
    "bridges": Folder(
        folders=frozenset({"common", "tools", PLATFORM}),
        files=frozenset({"__init__.py", "launcher.py", "bridges.manifest.json"}),
        owner="the bridges the app launches: what they all share, the tools, one folder per platform",
        never_below=frozenset({"runtime"}),
    ),
    "bridges/common": Folder(
        folders=frozenset(),
        files=frozenset({ANY_PYTHON}),
        owner="what every bridge shares, flat; the device primitives live in the core (taktik/core/shared/device/)",
    ),
    "bridges/<platform>": Folder(
        folders=frozenset({"common", "account", "agent", "automation", "cold_dm", "dm", "notifications", "persona",
                           "publish", "scraping", "tasks", "unfollow"}),
        files=frozenset({"__init__.py"}),
        owner="one folder per bridge, named with the vocabulary the platforms share; `common/` is what the "
              "bridges of the platform share",
        vocabulary=True,
    ),
    "bridges/<platform>/*": Folder(
        folders=frozenset(),
        files=frozenset({ANY_PYTHON}),
        owner="one bridge, flat: its entry named as its key of the manifest, its support next to it",
    ),
    "bridges/tiktok/automation": Folder(
        folders=frozenset({"inbox"}),
        files=frozenset({ANY_PYTHON}),
        owner="the TikTok automation bridge: its entry, its dispatcher and its flows; the inbox flows in `inbox/`",
    ),
    "bridges/tiktok/automation/inbox": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON}), owner="the inbox flows of the TikTok automation bridge",
    ),
    "bridges/tools": Folder(
        folders=frozenset({"lab", "schema"}),
        files=frozenset({"__init__.py"}),
        owner="what the app launches outside a platform: the Cartography Lab, the schema gate of the base",
    ),
    "bridges/tools/schema": Folder(
        folders=frozenset(), files=frozenset({"__init__.py", ENTRY}), owner="the schema gate of the base: its entry",
    ),
    "bridges/tools/lab": Folder(
        folders=frozenset({"actions", "action_test", "registry", "selector_test", "workflow_test",
                           "youtube_action_test"}),
        files=frozenset({"__init__.py", "events.py", ENTRY}),
        owner="the Cartography Lab and its benches: one entry per Lab bridge, the stdout of the benches, the rest "
              "by subdomain",
    ),
    "bridges/tools/lab/action_test": Folder(
        folders=frozenset({ANY_FOLDER, "bundles"}),
        files=lab_modules("action_bundle.py", "runner.py", "tracing.py"),
        owner="Action Tester and Cartography: the runner, its bundles, the tracing of the selectors",
    ),
    "bridges/tools/lab/action_test/bundles": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("__init__.py", "instagram.py", "tiktok.py"),
        owner="the bundle of each platform",
    ),
    "bridges/tools/lab/registry": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("actions.py"), owner="the registry of the Lab actions",
    ),
    "bridges/tools/lab/selector_test": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("request.py", "runner.py"), owner="the live selectors",
    ),
    "bridges/tools/lab/workflow_test": Folder(
        folders=frozenset({"config", "contracts", "execution", "observability", "platforms", "reporting"}),
        files=frozenset({"__init__.py"}),
        owner="the workflow bench, filed by responsibility",
    ),
    "bridges/tools/lab/workflow_test/config": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("catalog.py", "request.py"),
        owner="the catalogue and the requests of the bench",
    ),
    "bridges/tools/lab/workflow_test/contracts": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("dispatch.py"), owner="what the bench shares: results",
    ),
    "bridges/tools/lab/workflow_test/execution": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("dispatcher.py", "lifecycle.py", "runners.py", "session.py"),
        owner="lifecycle, session and dispatch of a bench run",
    ),
    "bridges/tools/lab/workflow_test/observability": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("__init__.py"), owner="the state and trace hooks",
    ),
    "bridges/tools/lab/workflow_test/platforms/instagram": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("dispatcher.py", "runners.py"),
        owner="the Instagram branch of the bench",
    ),
    "bridges/tools/lab/workflow_test/platforms/instagram/workflows": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("dm.py", "publish.py", "scraping.py"),
        owner="the Instagram workflow families of the bench",
    ),
    "bridges/tools/lab/workflow_test/platforms/tiktok": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("dispatcher.py", "runners.py"),
        owner="the TikTok branch of the bench",
    ),
    "bridges/tools/lab/workflow_test/platforms/tiktok/workflows": Folder(
        folders=frozenset({ANY_FOLDER}),
        files=lab_modules("automation.py", "dm.py", "publish.py", "scraping.py", "unfollow.py"),
        owner="the TikTok workflow families of the bench",
    ),
    "bridges/tools/lab/workflow_test/reporting": Folder(
        folders=frozenset({ANY_FOLDER}), files=lab_modules("report.py"), owner="the report of a bench run",
    ),
}

IgnoreCheck = Callable[[str], bool]


def tree_paths(root: Path = CORE) -> list[str]:
    """The files of the tree, relative to the root and written with `/`: tracked, or untracked and not
    ignored, and still on disk (a file deleted but not yet staged is gone)."""
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed in {root}: {result.stderr.decode('utf-8', 'replace').strip()}")
    listed = {path for path in result.stdout.decode("utf-8").split("\0") if path}
    return sorted(path for path in listed if (root / path).is_file())


def read_manifest(root: Path = CORE) -> dict:
    return json.loads((root / MANIFEST).read_text(encoding="utf-8-sig"))


def platforms_of(paths: Iterable[str]) -> frozenset[str]:
    """The platforms: the folders of `taktik/core/social_media/` that hold a file."""
    prefix = f"{PLATFORMS_FOLDER}/"
    return frozenset(path[len(prefix):].split("/", 1)[0] for path in paths
                     if path.startswith(prefix) and "/" in path[len(prefix):])


def entry_files(manifest: Mapping[str, Mapping[str, str]]) -> frozenset[str]:
    """The file of each bridge of the manifest (`bridges.instagram.dm.dm_bridge` -> `bridges/instagram/dm/dm_bridge.py`)."""
    return frozenset(module.replace(".", "/") + ".py" for bridges in manifest.values() for module in bridges.values())


#: One line of `git check-ignore -v`: `<source>:<line>:<pattern><TAB><path>`; the source may hold a drive letter.
CHECK_IGNORE_LINE = re.compile(r"^(?P<source>.*):(?P<line>\d+):(?P<pattern>[^\t]*)\t")


def git_ignores(path: str, root: Path = CORE) -> bool:
    """Would git ignore a new file at `path`? A rule that re-includes it (`!x`) is no ignore."""
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "-v", "--no-index", path],
                            capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore failed on {path}: {result.stderr.strip()}")
    matched = CHECK_IGNORE_LINE.match(result.stdout)
    return result.returncode == 0 and matched is not None and not matched.group("pattern").startswith("!")


def key_precision(key: str, folder: str, platforms: frozenset[str]) -> Optional[int]:
    """How many segments of `key` are patterns, when `key` describes `folder`; None when it does not."""
    key_parts, folder_parts = key.split("/"), folder.split("/")
    if len(key_parts) != len(folder_parts):
        return None
    patterns = 0
    for key_part, folder_part in zip(key_parts, folder_parts):
        if key_part == PLATFORM and folder_part in platforms or key_part == ANY_FOLDER:
            patterns += 1
        elif key_part != folder_part:
            return None
    return patterns


def rule_for(folder: str, platforms: frozenset[str], layout: Mapping[str, Folder]) -> Optional[Folder]:
    """The entry of the table for `folder`: the most precise key that describes it."""
    matches = [(precision, key) for key in layout
               if (precision := key_precision(key, folder, platforms)) is not None]
    return layout[min(matches)[1]] if matches else None


def children(paths: Sequence[str], folder: str) -> tuple[set[str], set[str]]:
    """The sub-folders and the files `folder` holds directly."""
    prefix = f"{folder}/"
    held_folders: set[str] = set()
    held_files: set[str] = set()
    for path in paths:
        if path.startswith(prefix):
            name, _, rest = path[len(prefix):].partition("/")
            (held_folders if rest else held_files).add(name)
    return held_folders, held_files


def folder_findings(folder: str, rule: Folder, paths: Sequence[str], platforms: frozenset[str],
                    entries: frozenset[str], is_ignored: IgnoreCheck) -> list[str]:
    prefix = f"{folder}/"
    held_folders, held_files = children(paths, folder)
    named_folders = rule.folders - PATTERNS
    named_files = rule.files - PATTERNS
    entries_here = {path[len(prefix):] for path in entries if path.startswith(prefix) and "/" not in path[len(prefix):]}
    errors: list[str] = []

    def folder_allowed(name: str) -> bool:
        return name in named_folders or ANY_FOLDER in rule.folders or (PLATFORM in rule.folders and name in platforms)

    def file_allowed(name: str) -> bool:
        return (name in named_files or (ANY_PYTHON in rule.files and name.endswith(".py"))
                or (ENTRY in rule.files and name in entries_here))

    for name in sorted(held_folders):
        if not folder_allowed(name):
            errors.append(f"{prefix}{name}/: a folder `{folder}/` does not list. Document its usage in AGENTS.md "
                          f"(Structure), then add it to LAYOUT in this gate.")
    for name in sorted(held_files):
        if file_allowed(name):
            continue
        if name.endswith(".py"):
            places = ", ".join(sorted(named_folders)) or "a folder of the table"
            errors.append(f"{prefix}{name}: no .py at the root of `{folder}/`, file it in its usage folder ({places}).")
        else:
            errors.append(f"{prefix}{name}: a file `{folder}/` does not list. Move it, or list it in LAYOUT "
                          f"with the reason it stays there.")
    if not rule.vocabulary:
        for name in sorted(named_folders - held_folders):
            errors.append(f"{prefix}{name}/: listed in LAYOUT but holds no file, drop the entry.")
        for name in sorted(named_files - held_files):
            errors.append(f"{prefix}{name}: listed in LAYOUT but gone, drop the entry.")
        if ENTRY in rule.files and not entries_here & held_files:
            errors.append(f"{prefix}: no bridge of {MANIFEST} lives here, its entry is gone.")
    for name in sorted(named_folders if not rule.vocabulary else named_folders & held_folders):
        if is_ignored(f"{prefix}{name}/new_file.py"):
            errors.append(f"{prefix}{name}/: git ignores it, a file added there would vanish from git status. "
                          f"Anchor or narrow the .gitignore rule (`git check-ignore -v {prefix}{name}/x.py`).")
    for path in paths:
        if path.startswith(prefix):
            below = path[len(prefix):].split("/")[:-1]
            for name in sorted(rule.never_below.intersection(below)):
                errors.append(f"{path}: no `{name}/` folder under `{folder}/`; the support of a bridge lives next "
                              f"to its entry, what a platform shares in its `common/`.")
    return errors


def manifest_findings(paths: Sequence[str], manifest: Mapping[str, Mapping[str, str]], platforms: frozenset[str],
                      layout: Mapping[str, Folder]) -> list[str]:
    """Each bridge of the manifest in its place, and no `*_bridge.py` that is not one of them."""
    bridge_folders = layout["bridges/<platform>"].folders - {"common"}
    tools = layout["bridges/tools"].folders
    present = set(paths)
    entries = entry_files(manifest)
    errors: list[str] = []
    for group, bridges in manifest.items():
        for key, module in bridges.items():
            parts = module.split(".")
            in_place = (len(parts) == 4 and parts[0] == "bridges" and parts[3] == key
                        and ((parts[1] in platforms and parts[2] in bridge_folders)
                             or (parts[1] == "tools" and parts[2] in tools)))
            if not in_place:
                errors.append(f"{MANIFEST}: {group}.{key} = {module} is neither bridges.<platform>.<bridge folder>."
                              f"{key} nor bridges.tools.<tool>.{key}.")
            if module.replace(".", "/") + ".py" not in present:
                errors.append(f"{MANIFEST}: {group}.{key} = {module}, its file is missing.")
    for path in paths:
        parts = path.split("/")
        in_a_bridge = len(parts) >= 4 and parts[0] == "bridges" and parts[1] in platforms
        if in_a_bridge and parts[-1].endswith("_bridge.py") and path not in entries:
            errors.append(f"{path}: in the folder of a bridge, only its entry is named `*_bridge.py` (an entry of "
                          f"{MANIFEST}); its class lives in `bridge.py`.")
    return errors


def check(paths: Sequence[str], is_ignored: IgnoreCheck = git_ignores, layout: Mapping[str, Folder] = LAYOUT,
          manifest: Optional[Mapping[str, Mapping[str, str]]] = None) -> list[str]:
    manifest = read_manifest() if manifest is None else manifest
    platforms = platforms_of(paths)
    entries = entry_files(manifest)
    folders = {"/".join(path.split("/")[:depth]) for path in paths for depth in range(1, path.count("/") + 1)}
    literal_keys = {key for key in layout if PLATFORM not in key.split("/") and ANY_FOLDER not in key.split("/")}
    errors: list[str] = []
    for folder in sorted(folders | literal_keys):
        rule = rule_for(folder, platforms, layout)
        if rule is not None:
            errors.extend(folder_findings(folder, rule, paths, platforms, entries, is_ignored))
    errors.extend(manifest_findings(paths, manifest, platforms, layout))
    return errors


def self_test_cases(paths: Sequence[str]) -> dict[str, dict]:
    """Each fake must turn the gate red by its rule; the real tree, unchanged, must not."""
    def fake(extra: Iterable[str] = (), without: str = "") -> list[str]:
        return [p for p in paths if not (without and p.startswith(without))] + list(extra)

    manifest = read_manifest()
    misplaced = json.loads(json.dumps(manifest))
    misplaced["instagram"]["cold_dm_bridge"] = "bridges.instagram.cold_dm.commands"
    return {
        "a .py at the root of scripts/": {"paths": fake(["scripts/stray_tool.py"]), "expect": "no .py at the root"},
        "another file at the root of scripts/": {"paths": fake(["scripts/notes.txt"]),
                                                 "expect": "a file `scripts/` does not list"},
        "a folder scripts/ does not list": {"paths": fake(["scripts/misc/tool.py"]),
                                            "expect": "a folder `scripts/` does not list"},
        "a listed folder left empty": {"paths": fake(without="scripts/lab/"), "expect": "holds no file"},
        "a listed file gone": {"paths": fake(without="scripts/install.sh"), "expect": "but gone"},
        "a listed folder git ignores": {"paths": fake(), "expect": "git ignores it",
                                        "is_ignored": lambda path: path.startswith("scripts/build/")},
        "utils back next to cli and core": {"paths": fake(["taktik/utils/x.py"]),
                                            "expect": "a folder `taktik/` does not list"},
        "locales back at the root of taktik": {"paths": fake(["taktik/locales/fr.py"]),
                                               "expect": "a folder `taktik/` does not list"},
        "a folder taktik/cli/ does not list": {"paths": fake(["taktik/cli/foo/x.py"]),
                                               "expect": "a folder `taktik/cli/` does not list"},
        "common back in the CLI": {"paths": fake(["taktik/cli/common/x.py"]),
                                   "expect": "a folder `taktik/cli/` does not list"},
        "a .py at the root of the CLI": {"paths": fake(["taktik/cli/helpers.py"]),
                                         "expect": "no .py at the root of `taktik/cli/`"},
        "a folder of commands that is no platform": {"paths": fake(["taktik/cli/commands/bar/x.py"]),
                                                     "expect": "a folder `taktik/cli/commands/` does not list"},
        "a folder inside the commands of a platform": {
            "paths": fake(["taktik/cli/commands/instagram/sub/x.py"]),
            "expect": "a folder `taktik/cli/commands/instagram/` does not list"},
        "a folder inside the menus": {"paths": fake(["taktik/cli/menus/sub/x.py"]),
                                      "expect": "a folder `taktik/cli/menus/` does not list"},
        "a file that is not Python in the CLI support": {"paths": fake(["taktik/cli/support/notes.txt"]),
                                                         "expect": "a file `taktik/cli/support/` does not list"},
        "a loose module next to the platforms": {"paths": fake(["taktik/core/social_media/helpers.py"]),
                                                 "expect": "no .py at the root of `taktik/core/social_media/`"},
        "a folder bridges/ does not list": {"paths": fake(["bridges/compat/diagnostics/x.py"]),
                                            "expect": "a folder `bridges/` does not list"},
        "a file at the root of bridges/": {"paths": fake(["bridges/foo.py"]), "expect": "no .py at the root of `bridges/`"},
        "a runtime/ in the folder of a bridge": {"paths": fake(["bridges/instagram/account/runtime/x.py"]),
                                                 "expect": "no `runtime/` folder under `bridges/`"},
        "a runtime/ deep in the Lab": {"paths": fake(["bridges/tools/lab/actions/instagram/runtime/x.py"]),
                                       "expect": "no `runtime/` folder under `bridges/`"},
        "a sub-folder in the folder of a bridge": {"paths": fake(["bridges/instagram/dm/helpers/x.py"]),
                                                   "expect": "a folder `bridges/instagram/dm/` does not list"},
        "a bridge folder out of the vocabulary": {"paths": fake(["bridges/instagram/engagement/x.py"]),
                                                  "expect": "a folder `bridges/instagram/` does not list"},
        "a file at the root of a platform": {"paths": fake(["bridges/tiktok/base.py"]),
                                             "expect": "no .py at the root of `bridges/tiktok/`"},
        "a folder under inbox/": {"paths": fake(["bridges/tiktok/automation/inbox/sub/x.py"]),
                                  "expect": "a folder `bridges/tiktok/automation/inbox/` does not list"},
        "a sub-folder of bridges/common/": {"paths": fake(["bridges/common/helpers/x.py"]),
                                            "expect": "a folder `bridges/common/` does not list"},
        "device back under bridges/common/": {"paths": fake(["bridges/common/device/connection.py"]),
                                              "expect": "a folder `bridges/common/` does not list"},
        "an unknown tool": {"paths": fake(["bridges/tools/other/x.py"]),
                            "expect": "a folder `bridges/tools/` does not list"},
        "a _bridge.py that is no entry": {"paths": fake(["bridges/instagram/dm/helper_bridge.py"]),
                                          "expect": "only its entry is named `*_bridge.py`"},
        "a flat module at the root of the Lab": {"paths": fake(["bridges/tools/lab/workflow_runner.py"]),
                                                 "expect": "no .py at the root of `bridges/tools/lab/`"},
        "an unknown subdomain of the Lab": {"paths": fake(["bridges/tools/lab/misc/x.py"]),
                                            "expect": "a folder `bridges/tools/lab/` does not list"},
        "a flat module at the root of the workflow bench": {
            "paths": fake(["bridges/tools/lab/workflow_test/runners.py"]),
            "expect": "no .py at the root of `bridges/tools/lab/workflow_test/`"},
        "an unknown folder of the workflow bench": {"paths": fake(["bridges/tools/lab/workflow_test/misc/x.py"]),
                                                    "expect": "a folder `bridges/tools/lab/workflow_test/` does not list"},
        "a Lab entry gone": {"paths": fake(without="bridges/tools/lab/selector_test_bridge.py"),
                             "expect": "its file is missing"},
        "a module of the Lab gone": {"paths": fake(without="bridges/tools/lab/action_test/runner.py"),
                                     "expect": "bridges/tools/lab/action_test/runner.py: listed in LAYOUT but gone"},
        "a value of the manifest out of its place": {"paths": fake(), "manifest": misplaced,
                                                     "expect": "is neither bridges.<platform>.<bridge folder>"},
    }


def caught(case: dict) -> bool:
    is_ignored = case.get("is_ignored", lambda _path: False)
    return any(case["expect"] in error for error in check(case["paths"], is_ignored, manifest=case.get("manifest")))


def self_test() -> int:
    paths = tree_paths()
    cases = self_test_cases(paths)
    missed = [name for name, case in cases.items() if not caught(case)]
    control = check(paths)
    if missed or control:
        for name in missed:
            print(f"Self-test FAILED, not caught: {name}")
        for error in control:
            print(f"Self-test FAILED, the real tree is red: {error}")
        return 1
    print(f"Tree layout self-test OK ({len(cases)} fakes caught, the real tree green)")
    return 0


def main() -> int:
    paths = tree_paths()
    errors = check(paths)
    if errors:
        print(f"Tree layout: {len(errors)} finding(s). The table is LAYOUT in this gate; AGENTS.md (Structure) "
              f"says what each folder is for.")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"Tree layout OK ({len(LAYOUT)} folder(s) of the table, {len(platforms_of(paths))} platforms, "
          f"{len(paths)} files, every one in its place)")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
