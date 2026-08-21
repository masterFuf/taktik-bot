"""clean_post_caption — the caption reduced to the author's actual words.

Every fixture below is a REAL pattern from the 556 stored AI comments: glued handle (89%),
trailing collapse control "moins" (72.7%), leftover "… plus" truncation marker (15%), and
dot-run captions whose emoji the XML dump ate (8.3% — the ones the model invented from).
"""

from taktik.core.social_media.instagram.workflows.core.caption_hygiene import (
    clean_post_caption,
)


def test_strips_author_handle_and_collapse_word():
    got = clean_post_caption(
        "pajaro.errante.tango.eclectric Août 2025 @cocogardeltango (Lausanne)\n"
        "Neolonga de Verano - Jean-Marc Vandel\n\nphotos ©Alexander Verkhovsky moins",
        author_hint="pajaro.errante.tango.eclectric",
    )
    assert got.author_prefix == "pajaro.errante.tango.eclectric"
    assert got.text.startswith("Août 2025")
    assert not got.text.endswith("moins")
    assert not got.truncated


def test_collab_caption_keeps_original_author_as_prefix():
    # Repost/collab: the caption starts with ANOTHER handle than the target profile.
    got = clean_post_caption(
        "johan.peigneguy Voici la suite de mon film réalisé dans le cadre de la session… plus",
        author_hint="marion_eyraud_joly",
    )
    assert got.author_prefix == "johan.peigneguy"
    assert got.truncated  # the "… plus" marker means the expansion failed
    assert got.text.startswith("Voici la suite")


def test_prose_first_word_is_never_eaten():
    # No digit/dot/underscore and not the known author: a real word, keep it.
    got = clean_post_caption("incroyable soirée au bord du lac", author_hint="someone_else")
    assert got.author_prefix is None
    assert got.text.startswith("incroyable")


def test_dot_run_caption_has_no_substance():
    got = clean_post_caption("_jimmy_gauthier ....", author_hint="_jimmy_gauthier")
    assert got.mangled
    assert not got.has_substance


def test_short_real_caption_has_no_substance_either():
    got = clean_post_caption("nxcxl_k Kala Nera", author_hint="nxcxl_k")
    assert not got.has_substance


def test_real_caption_has_substance():
    got = clean_post_caption(
        "ink.beauty.institut Portes ouvertes samedi, venez découvrir l'institut moins",
        author_hint="ink.beauty.institut",
    )
    assert got.has_substance
    assert not got.mangled


def test_empty_and_none_are_safe():
    assert clean_post_caption(None).text == ""
    assert not clean_post_caption("").has_substance


def test_hashtag_only_caption_has_no_substance():
    # Real case (2026-08-21 run, @ornevy.creation): only the vision analysis of the image
    # carried anything to react to — the caption itself says nothing.
    got = clean_post_caption(
        "ornevy.creation #Ornevy #LivrePhoto #Souvenirs #EntrepreneuriatFéminin #MadeInFrance",
        author_hint="ornevy.creation",
    )
    assert not got.has_substance


def test_prose_with_hashtags_still_has_substance():
    got = clean_post_caption(
        "ornevy.creation Vos plus beaux souvenirs mis en lumière #Ornevy #MadeInFrance",
        author_hint="ornevy.creation",
    )
    assert got.has_substance


def test_url_only_caption_has_no_substance():
    got = clean_post_caption("brand https://example.com/very/long/link", author_hint="brand")
    assert not got.has_substance
