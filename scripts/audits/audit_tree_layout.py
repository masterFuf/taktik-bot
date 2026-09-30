"""Layout of the engine's tree: a folder of the table holds only what the table lets it hold.

`LAYOUT` is the table of contents of the tree, written once: for a folder, the sub-folders and the files it
may hold directly, with its owner. A framework fixes its folders (`src/Controller`, `src/Command`...) so that
everyone knows where to look before opening a file; the table does the same and this gate keeps the tree to
it (AGENTS.md, section Structure). A new folder is documented in AGENTS.md first, then added here.

How to read an entry (`Folder`):

- a name listed in `folders` or `files` must be there, and what is not listed may not be there;
- a pattern widens what may be there and requires nothing: `ANY_FOLDER` (any sub-folder), `ANY_PYTHON` (any
  `.py` file), `ANY_JSON` (any `.json` file), `PLATFORM` (a platform), `ENTRY` (a bridge entry of
  `bridges/bridges.manifest.json` that lives in this folder, `<key>.py`; at least one must be there), `CODE` (a
  folder of tests that mirrors a folder of the code, and every folder below it too: see below);
- `vocabulary=True`: the listed names are a vocabulary, any of them may be there and none is required (not
  every platform has every kind of bridge);
- `never_below`: a folder name that may appear nowhere under the folder (no `runtime/` under `bridges/`; no
  `utils/`, `helpers/` nor `misc/` under `taktik/` and `bridges/`, names that say nothing of what a folder holds).

A key may hold `PLATFORM` (`bridges/<platform>`: the folder of each platform) or `*` (`bridges/<platform>/*`:
each folder its parent allows); the most precise key wins (`bridges/tiktok/automation` over
`bridges/<platform>/*`). The platforms are the folders of `taktik/core/social_media/`, read from the tree: the
one list of the platforms, never written by hand. The families of `taktik/core` stay listed once, in
`CORE_FAMILIES` of `audit_import_layers.py`, and that gate refuses a folder of `taktik/core` that is not a
family: the table does not repeat that rule (it has no entry for `taktik/core`).

The manifest of the bridges is read too: each value is `bridges.<platform>.<bridge folder>.<key>` or
`bridges.tools.<tool>.<key>` and its file exists, and in the folder of a bridge only its entry is named
`*_bridge.py`.

The inside of a platform is written once for every platform (tree lot 9, phase 3): what
`taktik/core/social_media/<platform>/` holds (`actions/`, `services/`, `ui/`, `workflows/`, its `manager.py`...) and
what its `workflows/` holds (one folder per feature, the vocabulary the bridges share, and `common/`). A platform
whose inside is not filed yet is named in `PLATFORMS_NOT_FILED`, one line each with why: those two entries skip it
(the rule `actions-no-workflows` of `audit_import_layers.py` holds for every platform since tree lot 11).

The tests follow the code, as `tests/` follows `src/` in a framework: a folder of `tests/unit/` mirrors a folder
of the code, at every depth. `tests/unit/<first>/<rest>` tests `<root>/<rest>`, where `<first>` names the root in
`MIRRORED_ROOTS` (`bridges`, `cli` for `taktik/cli`, `scripts`) or a family of the engine, `taktik/core/<first>`
(`tests/unit/kernel/` tests `taktik/core/kernel/`), read from the tree like the platforms. A theme suite is
declared by name in the entry of `tests/unit` (`one_path/`: the CLI and the bridge run the same path) and has its
own entry; a `fixtures/` folder holds the captures of the tests next to it; a mirrored folder holds Python files
only (a capture goes to `fixtures/`). At the root of `tests/unit/`: the tests of the package itself, of the
repository and of the harness. No folder of tests waits any more: the last ones, inside Instagram and TikTok,
follow their code since phase 3 of the tree reorganisation (tree lots 9 and 10).

The size of a folder is capped (tree lot 8): a folder holds at most so many `.py` files directly, 25 in the code
(`taktik/`, `bridges/`), 40 in the scripts and the tests (`scripts/`, `tests/unit/`), where a module of code may
have several test files; past it, a reader no longer takes the folder in at a glance, and it is split into
sub-folders by subject. The ceilings are fields of the table (`max_python`, set on the four roots; the nearest
entry on the way up decides). The folders above their ceiling today are listed with their count, one per line,
in `scripts/audits/audit_tree_layout_baseline.json`, written like the other ratchets (`ratchet.write_baseline`,
by `--update-baseline`). The list only shrinks: a listed folder that grows is red, and so is a folder above its
ceiling that the list does not name; a listed folder that shrinks or goes away is not red, the green line says
so and the next `--update-baseline` records it. To recompute the list on a tree other lots changed first, delete
the file and run `--update-baseline`: it freezes the state of the tree, as it did the day the gate was laid.

The files are the ones git has or would add: tracked, or untracked and not ignored (`git ls-files --cached
--others --exclude-standard`), still on disk. A script forgotten at the root of `scripts/` is seen before its
first commit, as a stray file of a working copy is (the private `audit_sqlite_schema_docs.py`, until it is
filed where `.gitignore` expects it); what git ignores is not part of the tree: the `__pycache__` folders
(`.gitignore`), a folder left with its caches only (`taktik/config/` in an old checkout), the build output.

The table today: `scripts/` filed by usage (tree lot 2), `taktik/` and its CLI (tree lot 3), the folder of the
platforms (tree lot 4), `bridges/` with its tools and the Cartography Lab (tree lot 5; the Lab layout gate of
the old tree, `audit_diagnostics_runtime_layout.py`, is folded in here), `bridges/common/` flat (tree lot 6: the
device primitives went to the core), `tests/unit/` (tree lot 7), the inside of the platforms (tree lots 9 and
10), the size of every folder (tree lot 8).

The gate is red when:

- a folder of the table holds a sub-folder or a file it does not let in (a `.py` at the root of `scripts/`:
  file it in its usage folder);
- an entry of the table no longer exists (a listed sub-folder without a file, a listed file gone): the table
  says what is there, drop the entry;
- git ignores a listed sub-folder: a file added there would vanish from `git status` (the unanchored `build/`
  of the `.gitignore` did it to `scripts/build/`);
- a folder named in `never_below` appears under its folder;
- a value of the bridges manifest is out of its place or its file is gone, or a `*_bridge.py` in the folder of a
  bridge is no entry;
- a folder of `tests/unit/` mirrors no folder of the code and is neither a declared theme suite nor a
  `fixtures/` folder; a mirrored folder holds a file that is not Python;
- an entry of `PLATFORMS_NOT_FILED` is no platform any more, or its inside keeps to the table now (drop it);
- a folder holds more `.py` files directly than its ceiling and the list of the oversized folders does not name
  it, or a listed folder holds more than its count in the list.

    python scripts/audits/audit_tree_layout.py                    # green / red
    python scripts/audits/audit_tree_layout.py --self-test        # each kind of misplaced entry turns it red
    python scripts/audits/audit_tree_layout.py --update-baseline  # record the oversized folders that shrank
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

from ratchet import Ratchet, enforce, load_baseline

CORE = Path(__file__).resolve().parents[2]
MANIFEST = "bridges/bridges.manifest.json"
PLATFORMS_FOLDER = "taktik/core/social_media"

PLATFORM = "<platform>"
ANY_FOLDER = "*"
ANY_PYTHON = "*.py"
ANY_JSON = "*.json"
ENTRY = "<entry>"
CODE = "<code>"
PATTERNS = frozenset({PLATFORM, ANY_FOLDER, ANY_PYTHON, ANY_JSON, ENTRY, CODE})

TESTS = "tests/unit"
FAMILIES_FOLDER = "taktik/core"
FIXTURES = "fixtures"
#: The roots a folder of `tests/unit/` mirrors, by its first folder; any other first folder is a family of the
#: engine, `taktik/core/<first>` (`tests/unit/kernel/` tests `taktik/core/kernel/`).
MIRRORED_ROOTS = {"bridges": "bridges", "cli": "taktik/cli", "scripts": "scripts"}

#: The most `.py` files a folder holds directly (`Folder.max_python`), in the code and in the scripts and tests.
#: On the final tree of the reorganisation, the largest folder of code holds 25 (the helpers of the Instagram
#: workflows) and the largest folder of scripts 29 (the gates); two folders of tests are above 40, listed.
CODE_CEILING = 25
SCRIPTS_AND_TESTS_CEILING = 40

#: Folder names that say nothing of what the folder holds: never a folder of the code (`never_below` of `taktik`
#: and `bridges`). A folder is named by its role, as the conventions of AGENTS.md (Structure) name them.
VAGUE_NAMES = frozenset({"helpers", "misc", "utils"})

#: The folders above their ceiling today, each with its count: a ratchet (`ratchet.py`), one folder per line.
SIZES = Ratchet(
    label="Folder sizes",
    noun=".py file(s)",
    remedy="Split the folder into sub-folders by subject.",
    command="python scripts/audits/audit_tree_layout.py",
    baseline=CORE / "scripts" / "audits" / "audit_tree_layout_baseline.json",
    unit="folder",
)

#: The platforms whose inside is not filed yet, and why. The two entries of LAYOUT for the inside of a platform skip
#: them. The list only shrinks: an entry that is no platform any more, or whose inside keeps to the table now, turns
#: the gate red.
PLATFORMS_NOT_FILED: dict[str, str] = {
    "threads": "core/manager.py (the word core) and its workflows as flat files of workflows/: the manager at its "
               "root, a workflows/automation/ folder",
    "gmail": "its workflows as flat files of workflows/ (account.py, agent_handler.py and their two helpers): a "
             "workflows/account/ folder",
}


@dataclass(frozen=True)
class Folder:
    """What a folder of the tree holds directly, and who owns it."""

    folders: frozenset[str]
    files: frozenset[str]
    owner: str
    vocabulary: bool = False
    never_below: frozenset[str] = frozenset()
    #: The most `.py` files a folder holds directly, for this folder and the folders below it: the nearest entry on
    #: the way up that sets one decides (`ceiling_for`).
    max_python: Optional[int] = None


def lab_modules(*names: str) -> frozenset[str]:
    """A folder of the Lab: any Python file, and these modules at least."""
    return frozenset({ANY_PYTHON, *names})


LAYOUT: dict[str, Folder] = {
    "scripts": Folder(
        folders=frozenset({"audits", "build", "dev", "eval", "generate", "hooks", "lab", "repairs"}),
        files=frozenset({"install.ps1", "install.sh"}),
        owner="the tooling, filed by usage; at the root, the public install commands only",
        max_python=SCRIPTS_AND_TESTS_CEILING,
    ),
    "taktik": Folder(
        folders=frozenset({"cli", "core"}),
        files=frozenset({"__init__.py", "__main__.py"}),
        owner="the package: its CLI and the engine (the families of `core/` are checked by audit_import_layers.py)",
        never_below=VAGUE_NAMES,
        max_python=CODE_CEILING,
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
    f"{PLATFORMS_FOLDER}/{PLATFORM}": Folder(
        folders=frozenset({"actions", "services", "ui", "workflows", "media", "recorder"}),
        files=frozenset({"__init__.py", "manager.py"}),
        owner="one platform, filed like the others: its gestures and readings (actions/), its business services "
              "(services/), its selectors and screen readers (ui/), its workflows (workflows/), its manager; "
              "Instagram adds its media capture (media/) and its session recorder (recorder/)",
        vocabulary=True,
    ),
    f"{PLATFORMS_FOLDER}/{PLATFORM}/workflows": Folder(
        folders=frozenset({"common", "account", "ads", "agent", "automation", "cold_dm", "dm", "notifications",
                           "publish", "scraping", "tasks"}),
        files=frozenset({"__init__.py", "README.md"}),
        owner="one folder per feature, named with the vocabulary the platforms and their bridges share; common/ is "
              "what the workflows of the platform share, their one folder of helpers",
        vocabulary=True,
    ),
    "bridges": Folder(
        folders=frozenset({"common", "tools", PLATFORM}),
        files=frozenset({"__init__.py", "launcher.py", "bridges.manifest.json"}),
        owner="the bridges the app launches: what they all share, the tools, one folder per platform",
        never_below=frozenset({"runtime"}) | VAGUE_NAMES,
        max_python=CODE_CEILING,
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
    TESTS: Folder(
        folders=frozenset({CODE, "one_path"}),
        files=frozenset({ANY_PYTHON}),
        owner="the unit tests, filed like the code they test (a folder mirrors a folder of the code, the captures "
              "of its tests in `fixtures/`); at the root, the tests of the package itself, of the repository and of "
              "the harness (conftest.py, its guards, the shared helpers); `one_path/`, a theme suite",
        max_python=SCRIPTS_AND_TESTS_CEILING,
    ),
    f"{TESTS}/one_path": Folder(
        folders=frozenset(), files=frozenset({ANY_PYTHON, ANY_JSON}),
        owner="the theme suite of rules 1 and 2 (the CLI and the bridge run the same path): its rigs, its tests and "
              "the bridge sequences they record",
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
        # CODE: the folder of tests is held to the code by tests_findings, at every depth
        return (name in named_folders or ANY_FOLDER in rule.folders or CODE in rule.folders
                or (PLATFORM in rule.folders and name in platforms))

    def file_allowed(name: str) -> bool:
        return (name in named_files or (ANY_PYTHON in rule.files and name.endswith(".py"))
                or (ANY_JSON in rule.files and name.endswith(".json")) or (ENTRY in rule.files and name in entries_here))

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
                errors.append(f"{path}: no `{name}/` folder under `{folder}/`; a folder is named by what it holds: "
                              f"the support of a bridge lives next to its entry, what a platform shares in its "
                              f"`common/`.")
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


def mirrored_folder(test_folder: str) -> str:
    """The folder of the code a folder of tests mirrors: `tests/unit/kernel` -> `taktik/core/kernel`,
    `tests/unit/bridges/tools/lab` -> `bridges/tools/lab`, `tests/unit/cli` -> `taktik/cli`."""
    first, _, rest = test_folder[len(TESTS) + 1:].partition("/")
    root = MIRRORED_ROOTS.get(first, f"{FAMILIES_FOLDER}/{first}")
    return f"{root}/{rest}" if rest else root


def tests_findings(paths: Sequence[str], folders: set[str], layout: Mapping[str, Folder]) -> list[str]:
    """Each folder of `tests/unit/` mirrors a folder of the code, or is a declared theme suite (its own entry) or a
    `fixtures/` folder; a mirrored folder holds Python files only."""
    rule = layout.get(TESTS)
    if rule is None or CODE not in rule.folders:
        return []
    suites = rule.folders - PATTERNS

    def held_to_the_code(folder: str) -> bool:
        parts = folder[len(TESTS) + 1:].split("/")
        return parts[0] not in suites and FIXTURES not in parts

    errors: list[str] = []
    for folder in sorted(f for f in folders if f.startswith(f"{TESTS}/") and held_to_the_code(f)):
        code = mirrored_folder(folder)
        if code not in folders:
            errors.append(f"{folder}/: no folder of the code is {code}/. A test goes to the folder of the code it "
                          f"tests (`tests/unit/<family>/` for `taktik/core/<family>/`, `tests/unit/bridges/...`, "
                          f"`tests/unit/cli/`, `tests/unit/scripts/`), or to a theme suite of LAYOUT.")
    for path in paths:
        folder, _, name = path.rpartition("/")
        if folder.startswith(f"{TESTS}/") and held_to_the_code(folder) and not name.endswith(".py"):
            errors.append(f"{path}: a folder of tests holds Python files; a capture or a recorded file goes to the "
                          f"`{FIXTURES}/` folder next to its tests.")
    return errors


def inside_of(folder: str) -> Optional[str]:
    """The platform whose inside `folder` is (`taktik/core/social_media/<platform>` or below), or None."""
    prefix = f"{PLATFORMS_FOLDER}/"
    return folder[len(prefix):].split("/", 1)[0] if folder.startswith(prefix) else None


def not_filed_findings(paths: Sequence[str], folders: set[str], platforms: frozenset[str],
                       layout: Mapping[str, Folder], not_filed: Mapping[str, str]) -> list[str]:
    """Each entry of PLATFORMS_NOT_FILED is a platform whose inside does not keep to the table yet."""
    errors: list[str] = []
    for platform in sorted(not_filed):
        root = f"{PLATFORMS_FOLDER}/{platform}"
        if platform not in platforms:
            errors.append(f"{root}/: listed in PLATFORMS_NOT_FILED but is no platform any more, drop the entry.")
            continue
        findings = []
        for folder in (root, f"{root}/workflows"):
            rule = rule_for(folder, platforms, layout)
            if rule is not None and folder in folders:
                findings += folder_findings(folder, rule, paths, platforms, frozenset(), lambda _path: False)
        if not findings:
            errors.append(f"{root}/: listed in PLATFORMS_NOT_FILED but its inside keeps to LAYOUT now, drop the entry.")
    return errors


def ceiling_for(folder: str, platforms: frozenset[str], layout: Mapping[str, Folder]) -> Optional[int]:
    """The most `.py` files `folder` may hold directly: the `max_python` of the nearest entry of the table, its own
    or one on the way up; None under a root that sets none."""
    parts = folder.split("/")
    for depth in range(len(parts), 0, -1):
        rule = rule_for("/".join(parts[:depth]), platforms, layout)
        if rule is not None and rule.max_python is not None:
            return rule.max_python
    return None


def oversized(paths: Sequence[str], platforms: frozenset[str], layout: Mapping[str, Folder]) -> dict[str, int]:
    """Each folder that holds more `.py` files directly than its ceiling, with its count."""
    held = Counter(folder for folder, _, name in (path.rpartition("/") for path in paths)
                   if folder and name.endswith(".py"))
    over: dict[str, int] = {}
    for folder, count in sorted(held.items()):
        ceiling = ceiling_for(folder, platforms, layout)
        if ceiling is not None and count > ceiling:
            over[folder] = count
    return over


def size_findings(over: Mapping[str, int], size_list: Mapping[str, int], platforms: frozenset[str],
                  layout: Mapping[str, Folder]) -> list[str]:
    """A folder above its ceiling that the list of the oversized folders does not name, or a listed folder that
    grew. A listed folder that shrinks or goes away is no finding (`size_notes`)."""
    errors: list[str] = []
    for folder, count in over.items():
        ceiling = ceiling_for(folder, platforms, layout)
        listed = size_list.get(folder)
        if listed is None:
            errors.append(f"{folder}/: more .py files than its ceiling of {ceiling} ({count}). Split it into "
                          f"sub-folders by subject; a test goes to the folder of the code it tests.")
        elif count > listed:
            errors.append(f"{folder}/: more .py files than the {listed} of the list ({count}; its ceiling is "
                          f"{ceiling}). A folder above its ceiling only shrinks: split it into sub-folders by subject.")
    return errors


def size_notes(over: Mapping[str, int], size_list: Mapping[str, int]) -> list[str]:
    """Each listed folder that holds fewer files than its count, or no longer more than its ceiling: not red, the
    next `--update-baseline` lowers or drops its line."""
    return [f"{folder}/ ({listed} listed, {over[folder] if folder in over else 'not above its ceiling any more'})"
            for folder, listed in sorted(size_list.items()) if over.get(folder, 0) < listed]


def check(paths: Sequence[str], is_ignored: IgnoreCheck = git_ignores, layout: Mapping[str, Folder] = LAYOUT,
          manifest: Optional[Mapping[str, Mapping[str, str]]] = None,
          not_filed: Mapping[str, str] = PLATFORMS_NOT_FILED,
          size_list: Optional[Mapping[str, int]] = None) -> list[str]:
    manifest = read_manifest() if manifest is None else manifest
    size_list = load_baseline(SIZES.baseline) if size_list is None else size_list
    platforms = platforms_of(paths)
    entries = entry_files(manifest)
    folders = {"/".join(path.split("/")[:depth]) for path in paths for depth in range(1, path.count("/") + 1)}
    literal_keys = {key for key in layout if PLATFORM not in key.split("/") and ANY_FOLDER not in key.split("/")}
    errors: list[str] = []
    for folder in sorted(folders | literal_keys):
        if inside_of(folder) in not_filed:
            continue  # its inside waits for phase 3 (PLATFORMS_NOT_FILED)
        rule = rule_for(folder, platforms, layout)
        if rule is not None:
            errors.extend(folder_findings(folder, rule, paths, platforms, entries, is_ignored))
    errors.extend(manifest_findings(paths, manifest, platforms, layout))
    errors.extend(tests_findings(paths, folders, layout))
    errors.extend(not_filed_findings(paths, folders, platforms, layout, not_filed))
    errors.extend(size_findings(oversized(paths, platforms, layout), size_list, platforms, layout))
    return errors


#: New folders of the fakes of the size rule: a fake folder holds exactly the files the fake writes in it.
FAKE_CODE_FOLDER = "taktik/core/kernel/fake_folder"
FAKE_BRIDGES_FOLDER = "bridges/tools/lab/action_test/fake_folder"
FAKE_SCRIPTS_FOLDER = "scripts/audits/fake_folder"
FAKE_TESTS_FOLDER = f"{TESTS}/kernel/fake_folder"


def fake_files(folder: str, count: int) -> list[str]:
    return [f"{folder}/fake_{index}.py" for index in range(count)]


def self_test_cases(paths: Sequence[str]) -> dict[str, dict]:
    """Each fake must turn the gate red by its rule; the real tree, unchanged, must not."""
    def fake(extra: Iterable[str] = (), without: str = "") -> list[str]:
        return [p for p in paths if not (without and p.startswith(without))] + list(extra)

    # A folder of tests mirrors a folder of the code: the fake folder of tests comes with its folder of code.
    tests_above = fake_files(FAKE_CODE_FOLDER, 1) + fake_files(FAKE_TESTS_FOLDER, SCRIPTS_AND_TESTS_CEILING + 1)
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
        # A vague name deep under the code, in a folder no other entry of the table describes: only `never_below`.
        # The names are written out, not read from VAGUE_NAMES: a name dropped from the list keeps its fake.
        **{f"a {name}/ folder deep under {root}/": {"paths": fake([f"{deep}/{name}/x.py"]),
                                                     "expect": f"no `{name}/` folder under `{root}/`"}
           for root, deep in (("taktik", "taktik/core/shared"), ("bridges", "bridges/tools/lab/action_test"))
           for name in ("helpers", "misc", "utils")},
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
        "the dissolved tests/unit/core/ back": {"paths": fake(["tests/unit/core/test_x.py"]),
                                                "expect": "no folder of the code is taktik/core/core/"},
        "a folder of tests no code has": {"paths": fake(["tests/unit/misc/test_x.py"]),
                                          "expect": "no folder of the code is taktik/core/misc/"},
        "a folder of tests below a family, not in the code": {"paths": fake(["tests/unit/kernel/sub/test_x.py"]),
                                                              "expect": "no folder of the code is taktik/core/kernel/sub/"},
        "the tests of the contract back under app/": {"paths": fake(["tests/unit/app/contract/test_x.py"]),
                                                      "expect": "no folder of the code is taktik/core/app/"},
        "the Lab tests back under their old path": {"paths": fake(["tests/unit/bridges/compat/diagnostics/test_x.py"]),
                                                    "expect": "no folder of the code is bridges/compat/"},
        "a runtime/ folder of tests under a bridge": {
            "paths": fake(["tests/unit/bridges/instagram/automation/runtime/test_x.py"]),
            "expect": "no folder of the code is bridges/instagram/automation/runtime/"},
        "a capture next to its tests": {"paths": fake(["tests/unit/shared/device/screen.xml"]),
                                        "expect": "goes to the `fixtures/` folder next to its tests"},
        "a file at the root of the tests that is not Python": {"paths": fake(["tests/unit/notes.txt"]),
                                                               "expect": "a file `tests/unit/` does not list"},
        "a folder inside the theme suite": {"paths": fake(["tests/unit/one_path/sub/x.py"]),
                                            "expect": "a folder `tests/unit/one_path/` does not list"},
        "the theme suite gone": {"paths": fake(without="tests/unit/one_path/"),
                                 "expect": "tests/unit/one_path/: listed in LAYOUT but holds no file"},
        "the word core back inside a filed platform": {
            "paths": fake([f"{PLATFORMS_FOLDER}/instagram/core/manager.py"]),
            "expect": f"a folder `{PLATFORMS_FOLDER}/instagram/` does not list"},
        "a loose module at the root of a filed platform": {
            "paths": fake([f"{PLATFORMS_FOLDER}/instagram/helpers.py"]),
            "expect": f"no .py at the root of `{PLATFORMS_FOLDER}/instagram/`"},
        "a folder of workflows out of the vocabulary": {
            "paths": fake([f"{PLATFORMS_FOLDER}/instagram/workflows/management/login_workflow.py"]),
            "expect": f"a folder `{PLATFORMS_FOLDER}/instagram/workflows/` does not list"},
        "a loose module among the workflows of another filed platform": {
            "paths": fake([f"{PLATFORMS_FOLDER}/youtube/workflows/helpers.py"]),
            "expect": f"no .py at the root of `{PLATFORMS_FOLDER}/youtube/workflows/`"},
        "a platform waiting for phase 3 that keeps to the table now": {
            "paths": fake([f"{PLATFORMS_FOLDER}/tiktok/__init__.py", f"{PLATFORMS_FOLDER}/tiktok/ui/selectors.py"],
                          without=f"{PLATFORMS_FOLDER}/tiktok/"),
            "not_filed": {**PLATFORMS_NOT_FILED, "tiktok": "a fake entry"},
            "expect": f"{PLATFORMS_FOLDER}/tiktok/: listed in PLATFORMS_NOT_FILED but its inside keeps to LAYOUT now"},
        "a platform waiting for phase 3 gone": {
            "paths": fake(without=f"{PLATFORMS_FOLDER}/gmail/"),
            "expect": f"{PLATFORMS_FOLDER}/gmail/: listed in PLATFORMS_NOT_FILED but is no platform any more"},
        # The size of a folder: one file past the ceiling of its root is red, a listed folder that grows too.
        "a folder of code above its ceiling": {
            "paths": fake(fake_files(FAKE_CODE_FOLDER, CODE_CEILING + 1)),
            "expect": f"{FAKE_CODE_FOLDER}/: more .py files than its ceiling of {CODE_CEILING} "},
        "a folder of the bridges above its ceiling": {
            "paths": fake(fake_files(FAKE_BRIDGES_FOLDER, CODE_CEILING + 1)),
            "expect": f"{FAKE_BRIDGES_FOLDER}/: more .py files than its ceiling of {CODE_CEILING} "},
        "a folder of scripts above its ceiling": {
            "paths": fake(fake_files(FAKE_SCRIPTS_FOLDER, SCRIPTS_AND_TESTS_CEILING + 1)),
            "expect": f"{FAKE_SCRIPTS_FOLDER}/: more .py files than its ceiling of {SCRIPTS_AND_TESTS_CEILING} "},
        "a folder of tests above its ceiling": {
            "paths": fake(tests_above),
            "expect": f"{FAKE_TESTS_FOLDER}/: more .py files than its ceiling of {SCRIPTS_AND_TESTS_CEILING} "},
        "a listed folder that grows": {
            "paths": fake(tests_above + [f"{FAKE_TESTS_FOLDER}/one_more.py"]),
            "size_list": {**load_baseline(SIZES.baseline), FAKE_TESTS_FOLDER: SCRIPTS_AND_TESTS_CEILING + 1},
            "expect": f"{FAKE_TESTS_FOLDER}/: more .py files than the {SCRIPTS_AND_TESTS_CEILING + 1} of the list"},
    }


def caught(case: dict) -> bool:
    is_ignored = case.get("is_ignored", lambda _path: False)
    errors = check(case["paths"], is_ignored, manifest=case.get("manifest"),
                   not_filed=case.get("not_filed", PLATFORMS_NOT_FILED), size_list=case.get("size_list"))
    return any(case["expect"] in error for error in errors)


def size_rule_left_alone(paths: Sequence[str]) -> bool:
    """What the size rule leaves green: a folder at its ceiling exactly (code 25, scripts 40, tests 40), a listed
    folder that shrinks, a listed folder gone; the two listed folders come back as notes."""
    at_the_ceiling = (fake_files(FAKE_CODE_FOLDER, CODE_CEILING)
                      + fake_files(FAKE_SCRIPTS_FOLDER, SCRIPTS_AND_TESTS_CEILING)
                      + fake_files(FAKE_TESTS_FOLDER, SCRIPTS_AND_TESTS_CEILING))
    shrunk = f"{TESTS}/kernel/shrunk_folder"
    gone = f"{TESTS}/kernel/gone_folder"
    tree = [*paths, *at_the_ceiling, *fake_files(shrunk, SCRIPTS_AND_TESTS_CEILING + 1)]
    # The folder of tests mirrors a folder of the code: its folder of code comes with it.
    tree += fake_files("taktik/core/kernel/shrunk_folder", 1)
    size_list = {**load_baseline(SIZES.baseline), shrunk: SCRIPTS_AND_TESTS_CEILING + 5,
                 gone: SCRIPTS_AND_TESTS_CEILING + 1}
    notes = size_notes(oversized(tree, platforms_of(tree), LAYOUT), size_list)
    noted = [note for note in notes if note.startswith((f"{shrunk}/", f"{gone}/"))]
    return check(tree, lambda _path: False, size_list=size_list) == [] and len(noted) == 2


def self_test() -> int:
    paths = tree_paths()
    cases = self_test_cases(paths)
    missed = [name for name, case in cases.items() if not caught(case)]
    if not size_rule_left_alone(paths):
        missed.append("a folder at its ceiling, a listed folder that shrinks or goes away, left green")
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
    platforms = platforms_of(paths)
    over = oversized(paths, platforms, LAYOUT)
    print(f"Tree layout OK ({len(LAYOUT)} folder(s) of the table, {len(platforms)} platforms, "
          f"{len(paths)} files, every one in its place; {len(platforms) - len(PLATFORMS_NOT_FILED)} platforms filed "
          f"inside, {len(PLATFORMS_NOT_FILED)} wait for phase 3; the tests mirror the code; {len(over)} folder(s) "
          f"above their ceiling, listed in {SIZES.baseline.name}, none grown)")
    notes = size_notes(over, load_baseline(SIZES.baseline))
    if notes:
        print(f"Note, not red: {len(notes)} listed folder(s) shrank or went away: {'; '.join(notes)}. "
              f"`{SIZES.command} --update-baseline` records it.")
    return 0


def update_size_list() -> int:
    """`--update-baseline`: the oversized folders of the tree, written through the ratchet, which refuses a rise."""
    paths = tree_paths()
    return enforce(oversized(paths, platforms_of(paths), LAYOUT), SIZES, update=True)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    raise SystemExit(update_size_list() if "--update-baseline" in sys.argv else main())
