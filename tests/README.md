# Tests layout

This folder separates runnable tests from local diagnostics.

## Versioned tests

`pytest` discovers tests under `tests/unit`, filed like the code they test, as `tests/` follows `src/` in a
framework: a folder of `tests/unit/` mirrors a folder of the code.

```text
tests/unit/
  kernel/  contract/  ai/  compat/  clone/  database/  shared/
      the families of the engine: tests/unit/<family>/ tests taktik/core/<family>/
  social_media/
      the platforms: tests/unit/social_media/<platform>/ tests taktik/core/social_media/<platform>/,
      at every depth (tests/unit/social_media/tiktok/workflows/dm/ tests its workflows/dm/)
  bridges/
      bridges/: common/, tools/lab/ (the Cartography Lab), tools/schema/, one folder per platform
  cli/
      taktik/cli/
  scripts/
      scripts/: the gates, the generators, the tooling
  one_path/
      a theme suite: the CLI and the bridge run the same path (rules 1 and 2)
  conftest.py, paths.py, android_shell.py
      the harness: its guards, CORE (the root of the core) and the shared helpers; at the root
      of tests/unit/ also live the tests of the package itself, of the repository and of the harness
```

A test goes to the folder of the code it tests. A path out of its own folder is written from `CORE`
(`from unit.paths import CORE`, then `CORE / "scripts/audits"`), so a test can move with its code; what it
reads next to it stays written from its own file (`Path(__file__).parent / "fixtures"`). A screen a test
reads is a real dump, anonymized, in a `fixtures/` folder (the captures a platform's tests share sit in
`tests/unit/social_media/<platform>/fixtures/`). `python scripts/audits/audit_tree_layout.py` keeps the
layout: a folder of `tests/unit/` that mirrors no folder of the code turns it red.

## Local diagnostics

The following folders are intentionally ignored by Git:

```text
tests/poc/
  One-off experiments and media extraction proofs of concept.
tests/smoke/
  Device-dependent smoke scripts.
```

Do not put reusable assertions in POC or smoke scripts. If a check protects
against a regression, move it to the folder of `tests/unit/` that mirrors the code it tests.

## Commands

```bash
python -m pytest
python -m pytest tests/unit/social_media/tiktok/workflows/publish
python -m pytest tests/unit/kernel tests/unit/contract
```
