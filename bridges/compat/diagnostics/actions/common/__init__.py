"""Diagnostic actions that are the same on every platform.

Each platform owns its own `ActionRegistry`, so a shared action is a plain function here that both
platforms REGISTER under the same id — one implementation, one id, two entries. Writing it twice
under `instagram/` and `tiktok/` is how `app.launch` ended up existing in two spellings.
"""
