# Tests layout

This folder separates runnable tests from local diagnostics.

## Versioned tests

`pytest` discovers tests under `tests/unit`.

```text
tests/unit/
  database/
    SQLite schema and local database service tests.
  social_media/
    tiktok/
      bridges/
        Bridge payload/event adapter tests.
      services/
        Reusable TikTok service tests.
      ui/
        Selectors, detectors and localization tests.
      workflows/
        followers/
          Followers workflow contracts.
        publish/
          TikTok publishing workflow/service tests.
```

## Local diagnostics

The following folders are intentionally ignored by Git:

```text
tests/poc/
  One-off experiments and media extraction proofs of concept.
tests/smoke/
  Device-dependent smoke scripts.
```

Do not put reusable assertions in POC or smoke scripts. If a check protects
against a regression, move it to `tests/unit/<domain>/<family>/`.

## Commands

```bash
python -m pytest
python -m pytest tests/unit/social_media/tiktok/workflows/publish
python -m pytest tests/unit/database
```
