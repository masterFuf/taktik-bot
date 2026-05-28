from taktik.core.social_media.tiktok.services.publish_caption import (
    build_caption,
    sanitize_caption_and_hashtags,
)


def test_sanitize_caption_extracts_dedupes_and_limits_hashtags():
    caption, hashtags, dropped = sanitize_caption_and_hashtags(
        "Hello #Paris #Travel\n\n\nFrom TikTok #paris",
        ["#Food", "food", "music", "art", "extra"],
    )

    assert caption == "Hello\n\nFrom TikTok"
    assert hashtags == ["paris", "travel", "food", "music", "art"]
    assert dropped == 1


def test_build_caption_keeps_text_and_hashtags_separated():
    assert build_caption("Hello", ["paris", "#travel"]) == "Hello\n#paris #travel"
    assert build_caption("", ["paris"]) == "#paris"
    assert build_caption("Hello", []) == "Hello"
