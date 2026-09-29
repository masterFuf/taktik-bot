"""Instagram automation config for compat workflow diagnostics.

The bench does NOT build this config itself any more. It assembles the same camelCase payload
the desktop bridge sends and hands it to the PRODUCTION launcher, `run_instagram_automation`,
which builds the config and the engine exactly as for a page run. The profile-filter toggles
(`allowPrivate`, `allowVerified`, `allowBusiness`) travel in that payload like the page's.

It used to keep a parallel builder, and every setting added to a workflow page had to be
re-declared here. None ever was, so the bench quietly drifted behind production:

  - a feed run carried none of the acquisition options (`interactWithPostAuthor`,
    `interactWithPostLikers`, `maxLikersPerPost`, `skipReels`) — it scrolled and liked, and
    never visited an author or opened a post's likers;
  - a hashtag run carried none of the plan keys, so `resolve_interaction_plan` fell through
    to the legacy exclusive mode. The bench validated ONE post and its likers — a shape the
    production page no longer emits.

A green run on a divergent config proves nothing about production, which is the one thing
this bench exists to do.
"""

# Bench workflow value -> the vocabulary the production builder speaks. Explicit rather than a
# pass-through because that builder fails loudly on an unknown type instead of guessing, and
# because the two vocabularies genuinely differ (`hashtag` here, `hashtags` there).
_PROD_WORKFLOW_TYPES = {
    "target_followers": "target_followers",
    "target_following": "target_following",
    "hashtag": "hashtags",
    "post_likers": "post_url",
    "post_url": "post_url",
    "feed": "feed",
    "unfollow": "unfollow",
}


def build_workflow_payload(
    workflow_type: str,
    target: str,
    limits: dict,
    probs: dict,
    session_duration: int = 30,
    delays: dict | None = None,
    filters: dict | None = None,
    max_consecutive_known: int | None = None,
    behavior_policy: dict | None = None,
    options: dict | None = None,
) -> dict:
    """The page payload of a bench run, for the production launcher to build and run.

    ``options`` carries the page-level settings verbatim (`engagePosts`, `walkLikers`,
    `feed: {...}`, …). It is deliberately opaque here: the production builder owns their
    whitelist, so a NEW page setting reaches the bench without touching this file — which is
    the whole point of delegating.
    """
    prod_type = _PROD_WORKFLOW_TYPES.get(workflow_type)
    if prod_type is None:
        raise ValueError(f"Unknown bench automation workflow type {workflow_type!r}")

    raw_config: dict = {
        "target": target,
        "workflowType": prod_type,
        "limits": {
            "maxProfiles": limits.get("maxProfiles", 3),
            "minLikesPerProfile": limits.get("minLikesPerProfile", 1),
            "maxLikesPerProfile": limits.get("maxLikesPerProfile", 1),
        },
        "probabilities": {
            "like": probs.get("like", 80),
            "follow": probs.get("follow", 0),
            "comment": probs.get("comment", 0),
            "watchStories": probs.get("watchStories", 0),
            "likeStories": probs.get("likeStories", 0),
        },
        # The bench's filter card is permissive by default where production is restrictive;
        # seeding the keys keeps the bench's own defaults instead of inheriting the other set.
        "filters": _filters_payload(filters or {}),
        "session": _session_payload(session_duration, delays, max_consecutive_known),
    }
    if behavior_policy:
        raw_config["behaviorPolicy"] = behavior_policy
    for key, value in (options or {}).items():
        raw_config[key] = value
    if prod_type == "hashtags":
        _seed_legacy_hashtag_plan(raw_config, raw_config["limits"]["maxProfiles"])
    return raw_config


def _seed_legacy_hashtag_plan(raw_config: dict, max_interactions: int) -> None:
    """Give a caller that states no plan the bench's historical hashtag behaviour.

    The production builder always WRITES the three plan keys, even as ``None``, and
    ``resolve_interaction_plan`` keys off their PRESENCE — so an absent plan no longer falls
    through to the legacy mode, it yields a plan with all three false: a run that opens posts
    and engages nothing. The front always states a plan; this covers everyone else by
    reproducing what the legacy `likers` mode did — one post, its likers walked up to the
    interaction budget.
    """
    if any(key in raw_config for key in ("engagePosts", "walkLikers", "walkCommenters")):
        return
    raw_config["engagePosts"] = False
    raw_config["walkLikers"] = True
    raw_config["walkCommenters"] = False
    raw_config.setdefault("maxPosts", 1)
    raw_config.setdefault("maxLikersPerPost", max_interactions)


def _filters_payload(f: dict) -> dict:
    payload = dict(f)
    payload.setdefault("minFollowers", 0)
    payload.setdefault("maxFollowers", 999999999)
    payload.setdefault("minPosts", 0)
    payload.setdefault("maxFollowing", 999999999)
    return payload


def _session_payload(session_duration: int, delays: dict | None, max_consecutive_known: int | None) -> dict:
    payload: dict = {"durationMinutes": session_duration}
    # Explicit delays win for back-compat; absent => the pacing profile drives the rhythm,
    # exactly like the production path.
    if delays:
        payload["minDelay"] = delays.get("min")
        payload["maxDelay"] = delays.get("max")
    if max_consecutive_known is not None:
        payload["maxConsecutiveKnownUsernames"] = max_consecutive_known
    return payload


__all__ = ["build_workflow_payload"]
