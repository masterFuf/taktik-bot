"""clean_post_caption — the caption reduced to the author's actual words.

Every fixture below is a REAL pattern from the 556 stored AI comments: glued handle (89%),
trailing collapse control "moins" (72.7%), leftover "… plus" truncation marker (15%), and
dot-run captions whose emoji the XML dump ate (8.3% — the ones the model invented from).
"""

from taktik.core.social_media.instagram.ui.caption_hygiene import (
    clean_post_caption,
)


def test_strips_author_handle_and_collapse_word():
    got = clean_post_caption(
        "demo.tango.club Août 2025 @demo_milonga (Lausanne)\n"
        "Neolonga de Verano - Jean-Marc Dupont\n\nphotos ©Alex Martin moins",
        author_hint="demo.tango.club",
    )
    assert got.author_prefix == "demo.tango.club"
    assert got.text.startswith("Août 2025")
    assert not got.text.endswith("moins")
    assert not got.truncated


def test_collab_caption_keeps_original_author_as_prefix():
    # Repost/collab: the caption starts with ANOTHER handle than the target profile.
    got = clean_post_caption(
        "johan.demo Voici la suite de mon film réalisé dans le cadre de la session… plus",
        author_hint="marion_demo",
    )
    assert got.author_prefix == "johan.demo"
    assert got.truncated  # the "… plus" marker means the expansion failed
    assert got.text.startswith("Voici la suite")


def test_prose_first_word_is_never_eaten():
    # No digit/dot/underscore and not the known author: a real word, keep it.
    got = clean_post_caption("incroyable soirée au bord du lac", author_hint="someone_else")
    assert got.author_prefix is None
    assert got.text.startswith("incroyable")


def test_dot_run_caption_has_no_substance():
    got = clean_post_caption("_jimmy_demo ....", author_hint="_jimmy_demo")
    assert got.mangled
    assert not got.has_substance


def test_short_real_caption_has_no_substance_either():
    got = clean_post_caption("demox_k Kala Nera", author_hint="demox_k")
    assert not got.has_substance


def test_real_caption_has_substance():
    got = clean_post_caption(
        "demo.beauty.institut Portes ouvertes samedi, venez découvrir l'institut moins",
        author_hint="demo.beauty.institut",
    )
    assert got.has_substance
    assert not got.mangled


def test_empty_and_none_are_safe():
    assert clean_post_caption(None).text == ""
    assert not clean_post_caption("").has_substance


def test_hashtag_only_caption_has_no_substance():
    # Real case (2026-08-21 run, @demovy.creation): only the vision analysis of the image
    # carried anything to react to — the caption itself says nothing.
    got = clean_post_caption(
        "demovy.creation #Demovy #LivrePhoto #Souvenirs #EntrepreneuriatFéminin #MadeInFrance",
        author_hint="demovy.creation",
    )
    assert not got.has_substance


def test_prose_with_hashtags_still_has_substance():
    got = clean_post_caption(
        "demovy.creation Vos plus beaux souvenirs mis en lumière #Demovy #MadeInFrance",
        author_hint="demovy.creation",
    )
    assert got.has_substance


def test_url_only_caption_has_no_substance():
    got = clean_post_caption("brand https://example.com/very/long/link", author_hint="brand")
    assert not got.has_substance
