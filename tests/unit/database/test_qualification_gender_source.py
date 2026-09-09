"""The gender was in the base and the decoder was reading the wrong place.

Four links, each cut: the read model did not expose `ai_gender`, the query did not select it,
and `_decode` read `analysis_json` -- which carries a gender in only ~10 % of the rows whose
COLUMN is filled (3 000 classified profiles, 2026-09-09; where both exist they agree 306/306).

Pinned because the failure is silent: wired only at the last step, the prompt would have carried
a confident agreement rule for one profile in ten and an empty string for the rest, with every
other test still green.
"""

from taktik.core.database.profile_qualification import ProfileQualification


def row(**over):
    base = {"username": "u", "niche": "n", "profession_tags": "[]", "analysis_json": None}
    base.update(over)
    return base


def test_the_column_answers_when_the_json_is_silent():
    """The 90 % case, and the whole reason this file exists."""
    assert ProfileQualification._decode(row(ai_gender="female"))["gender"] == "female"


def test_the_json_still_answers_when_the_column_is_empty():
    """Older rows carry it only there; dropping that path would trade one blind spot for another."""
    decoded = ProfileQualification._decode(row(ai_gender="", analysis_json='{"gender": "male"}'))
    assert decoded["gender"] == "male"


def test_neither_source_yields_an_empty_string_not_none():
    """The prompt builder branches on the value, so the contract is a string, always."""
    assert ProfileQualification._decode(row())["gender"] == ""


def test_a_brand_survives_decoding():
    """7 426 classified profiles are brands, and that verdict must reach the writer intact."""
    assert ProfileQualification._decode(row(ai_gender="brand"))["gender"] == "brand"


def test_an_older_app_database_reads_null_instead_of_failing():
    """`profile_qualification` belongs to the desktop app, so its shape follows the APP's version.

    `ai_gender` arrived after the niche columns, so a base served by an older app has the table
    without it. Selecting it blindly would fail the whole query and take the niche down with it —
    the profile would read as unclassified and get re-sent to the vision model.
    """
    import sqlite3

    from taktik.core.database.repositories.instagram.profile_ai_read_model import (
        profile_ai_read_model,
    )

    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE instagram_profiles (profile_id INTEGER, username TEXT)")
    old.execute("CREATE TABLE profile_qualification (username TEXT, ai_niche TEXT)")
    assert profile_ai_read_model(old, "p")["gender"] == "NULL"

    current = sqlite3.connect(":memory:")
    current.execute("CREATE TABLE instagram_profiles (profile_id INTEGER, username TEXT)")
    current.execute("CREATE TABLE profile_qualification (username TEXT, ai_gender TEXT)")
    assert profile_ai_read_model(current, "p")["gender"] == "pq.ai_gender"
