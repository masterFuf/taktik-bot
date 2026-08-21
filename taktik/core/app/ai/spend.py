"""What an AI call was PAID FOR — the vocabulary of the cost ledger.

A session used to report one opaque `ai_total_cost_usd`. The counters beside it
(`ai_profiles_analyzed`, `ai_posts_analyzed`, `ai_comments_generated`) told how MANY calls
of some kinds happened, but never what each kind cost — and several paid kinds had no
counter at all (engagement verdicts, batch username classification, agent decisions), so
the split could not even be derived by division.

These constants are that missing axis. They are a CLOSED vocabulary shared by the bot (which
tags every `ai_spend` event) and the desktop (which groups by them): one spelling, declared
once, so a breakdown can never silently split across two spellings of the same thing —
`profile` and `profile_analysis` would each look like half the truth.

Adding a kind means adding it HERE and nowhere else; a call that names an unknown kind falls
back to `other` rather than inventing a category.
"""

AI_SPEND_PROFILE = "profile"       # classify_profile_niche / analyze_profile_screenshot
AI_SPEND_POST = "post"             # analyze_post — the vision look at a post before commenting
AI_SPEND_COMMENT = "comment"       # generate_smart_comment / generate_comment_reply
AI_SPEND_VERDICT = "verdict"       # engagement_verdict — is this profile worth engaging?
AI_SPEND_AUDIENCE = "audience"     # classify_following_usernames_batch — audience/persona signals
AI_SPEND_DECISION = "decision"     # Taktik Agent autonomous decisions
AI_SPEND_DM = "dm"                 # direct-message generation
AI_SPEND_AD = "ad"                 # ad_analysis — the sponsored-post watch corpus
AI_SPEND_HASHTAGS = "hashtags"     # autopilot hashtag suggestions
AI_SPEND_OTHER = "other"           # anything not yet categorised — never a silent new bucket

AI_SPEND_KINDS = (
    AI_SPEND_PROFILE,
    AI_SPEND_POST,
    AI_SPEND_COMMENT,
    AI_SPEND_VERDICT,
    AI_SPEND_AUDIENCE,
    AI_SPEND_DECISION,
    AI_SPEND_DM,
    AI_SPEND_AD,
    AI_SPEND_HASHTAGS,
    AI_SPEND_OTHER,
)


def normalize_spend_kind(kind: str) -> str:
    """Fold a kind to the closed vocabulary; anything unknown becomes `other`."""
    value = (kind or "").strip().lower()
    return value if value in AI_SPEND_KINDS else AI_SPEND_OTHER


__all__ = [
    "AI_SPEND_KINDS", "normalize_spend_kind",
    "AI_SPEND_PROFILE", "AI_SPEND_POST", "AI_SPEND_COMMENT", "AI_SPEND_VERDICT",
    "AI_SPEND_AUDIENCE", "AI_SPEND_DECISION", "AI_SPEND_DM", "AI_SPEND_AD",
    "AI_SPEND_HASHTAGS", "AI_SPEND_OTHER",
]
