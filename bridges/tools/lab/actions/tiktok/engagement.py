"""Engagement runs of the TikTok Lab: the direct loop of a « Ces comptes » run."""

from bridges.tools.lab.actions.tiktok import action
from bridges.tools.lab.action_test.action_bundle import bundle_raw_device, lab_account_username, open_bot_base
from bridges.tools.lab.action_test.params import lab_int
from taktik.core.social_media.tiktok.workflows.automation.target_profiles.agent_handler import (
    run_tiktok_target_profiles,
)


@action("tt.engagement.target_profiles")
def target_profiles(a, p):
    """Visit the listed accounts themselves, as the Followers page runs « Ces comptes »
    (`target_profiles`): the run's launcher (`run_tiktok_target_profiles`), so the payload is read by
    the run's readers and the loop is `TargetProfilesWorkflow`: each handle searched on the Users tab,
    its profile checked, the planned gestures made, then back to the feed before the next one.
    Params: usernames (required, comma-separated), account (required: the run files its visits under
    the account and skips the profiles it already handled for it, as a run does; without it nothing
    is touched), like_percentage, follow_percentage, favorite_percentage, story_like_percentage
    (0-100 as the page sets them, 0 by default here: visits only), posts (videos opened per profile,
    1 by default, 0 when every gesture is at 0)."""
    usernames = [name.strip().lstrip("@") for name in str(p.get("usernames") or "").split(",") if name.strip()]
    if not usernames:
        return {"success": False, "message": "usernames param is required (comma-separated)"}
    account = lab_account_username(p)
    if not account:
        return {"success": False,
                "message": "account param is required: the run files its visits under the account and skips "
                           "the profiles it already handled, as a run does (nothing touched)"}
    gestures = {
        "likeProbability": lab_int(p, "like_percentage", 0),
        "followProbability": lab_int(p, "follow_percentage", 0),
        "favoriteProbability": lab_int(p, "favorite_percentage", 0),
        "storyLikeProbability": lab_int(p, "story_like_percentage", 0),
        "commentProbability": 0,
    }
    open_bot_base()
    posts = lab_int(p, "posts", 1) if any(gestures.values()) else 0
    outcome = run_tiktok_target_profiles(
        {
            "workflowType": "target_profiles",
            "profiles": usernames,
            "maxProfiles": len(usernames),
            "botUsername": account,
            "minPostsPerProfile": posts,
            "maxPostsPerProfile": posts,
            **gestures,
        },
        device=bundle_raw_device(a),
    )
    stats = outcome["stats"]
    reason = stats.get("completion_reason")
    return {"success": reason not in (None, "unknown") and stats.get("errors", 0) < len(usernames),
            "message": (f"{len(usernames)} profile(s): {stats.get('profiles_visited', 0)} visited, "
                        f"{stats.get('likes', 0)} like(s), {stats.get('follows', 0)} follow(s), "
                        f"{stats.get('errors', 0)} not reached; end: {reason}"),
            "details": stats}
