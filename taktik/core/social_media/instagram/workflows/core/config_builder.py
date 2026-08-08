"""Bridge-compatible config builder for Instagram automation workflows."""

import math
from typing import Any, Dict, Optional

from loguru import logger

from ...actions.business.workflows.common.distribution import normalize_distribution

# Workflow types this builder can turn into an automation action. Anything else must
# fail loudly instead of silently becoming a follower-interaction run (that fallback
# already bit once: an unmapped 'cold_dm' launched the wrong workflow on a real device).
SUPPORTED_WORKFLOW_TYPES = (
    "target_followers",
    "target_following",
    "hashtags",
    "post_url",
    "unfollow",
    "sync_following",
    "sync_followers_following",
    "feed",
)


def _build_action_config(
    *,
    raw_config: Dict[str, Any],
    action_type: str,
    interaction_type: str,
    primary_target: str,
    target_list: list[str],
    max_profiles: int,
    min_likes_per_profile: int,
    max_likes_per_profile: int,
    like_percentage: int,
    follow_percentage: int,
    comment_percentage: int,
    story_percentage: int,
    story_like_percentage: int,
    max_consecutive_known_usernames: Optional[int] = None,
    max_no_new_usernames_scrolls: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the action payload consumed by ``InstagramAutomation``."""

    target = raw_config.get("target")
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    comments_config = raw_config.get("comments", {})
    feed_stories_config = raw_config.get("feedStories", {})
    unfollow_config = raw_config.get("unfollow", {})
    post_criteria_config = raw_config.get("postCriteria") or {}

    if action_type == "sync_following":
        return {
            "type": "sync_following",
        }

    if action_type == "sync_followers_following":
        sync_cfg = raw_config.get("sync", {})
        return {
            "type": "sync_followers_following",
            "mode": sync_cfg.get("mode", "fast"),
        }

    if action_type == "unfollow":
        return {
            "type": "unfollow",
            "max_unfollows": unfollow_config.get("maxUnfollows", max_profiles),
            "unfollow_mode": unfollow_config.get("unfollowMode", "non-followers"),
            "min_delay": 2,
            "max_delay": 5,
            "skip_verified": unfollow_config.get("skipVerified", True),
            "skip_business": unfollow_config.get("skipBusiness", False),
            "min_days_since_follow": unfollow_config.get("minDaysSinceFollow", 3),
            "bot_follows_only": unfollow_config.get("botFollowsOnly", False),
            "whitelist": unfollow_config.get("whitelist", []),
            "blacklist": unfollow_config.get("blacklist", []),
        }

    if action_type == "feed":
        feed_story_enabled = bool(feed_stories_config.get("enabled", story_percentage > 0))
        feed_config = raw_config.get("feed", {})
        return {
            "type": "feed",
            "max_interactions": max_profiles,
            "max_posts_to_check": max_profiles,
            "like_percentage": like_percentage,
            "follow_percentage": follow_percentage,
            "comment_percentage": comment_percentage,
            "story_watch_percentage": story_percentage,
            "story_like_percentage": story_like_percentage,
            "view_feed_stories": feed_story_enabled,
            "max_feed_story_profiles": feed_stories_config.get(
                "maxProfiles", limits.get("maxFeedStoryProfiles", 5)
            ),
            "feed_story_reaction_percentage": probabilities.get("feedStoryReaction", 0),
            "feed_story_reaction": feed_stories_config.get("reaction", "laugh"),
            "min_post_likes": filters.get("minPostLikes", 0),
            "max_post_likes": filters.get("maxPostLikes", 0),
            "custom_comments": comments_config.get("customComments", []),
            # Human crawl toggles (default ON; future per-account bot settings).
            "skip_suggested": feed_config.get("skipSuggested", True),
            "read_captions": feed_config.get("readCaptions", True),
            "browse_carousels": feed_config.get("browseCarousels", True),
            # Recolte des PUBLICITES croisees pendant le run. Le crawl reconnait deja les
            # posts sponsorises pour les eviter ; active, il les enregistre au passage au
            # lieu de jeter cette reconnaissance. OFF par defaut, aucune pub n'est ouverte.
            "capture_ads": bool(feed_config.get("captureAds", False)),
            # Acquisition depuis le fil : visiter l'auteur du post, parcourir ses
            # likers, sauter les reels. Whitelist — sans ces entrees le reglage de la
            # page n'atteint jamais le workflow.
            "interact_with_post_author": bool(feed_config.get("interactWithPostAuthor", False)),
            "interact_with_post_likers": bool(feed_config.get("interactWithPostLikers", False)),
            "max_likers_per_post": int(feed_config.get("maxLikersPerPost", 5) or 5),
            "skip_reels": bool(feed_config.get("skipReels", False)),
            # Mode "follow des suggestions" : quand le carousel "Suggested for you"
            # apparait dans le feed, ouvrir "See all" et follow en masse depuis
            # Discover people. OFF par defaut ; ni follow-back ni demandes de suivi.
            "follow_suggestions": bool(feed_config.get("followSuggestions", False)),
            # Run "suggestions seules" : le feed n'est qu'un couloir vers le carousel,
            # aucun like / commentaire / story n'est fait.
            "suggestions_only": bool(feed_config.get("suggestionsOnly", False)),
            "max_carousel_scrolls": int(feed_config.get("maxCarouselScrolls", 12) or 0),
            "max_suggestion_follows": int(feed_config.get("maxSuggestionFollows", 20) or 0),
            "suggestions_contacts_choice": (
                "allow" if feed_config.get("allowContactsAccess", False) else "deny"
            ),
            "max_suggestion_passes": int(feed_config.get("maxSuggestionPasses", 1) or 0),
        }

    action_config: Dict[str, Any] = {
        "type": action_type,
        "target_username": primary_target if action_type == "interact_with_followers" else None,
        "target_usernames": target_list if action_type == "interact_with_followers" else [],
        # Singular keys carry the FIRST entry (back-compat readers); the plural lists are
        # what the multi-source runners iterate. `target` used to go through raw for
        # hashtags, so several hashtags reached the bot as one comma-joined string and
        # the run searched Instagram for the literal tag "tag1,tag2".
        "hashtag": primary_target if action_type == "hashtag" else None,
        "hashtags": target_list if action_type == "hashtag" else [],
        "post_url": primary_target if action_type == "post_url" else None,
        "post_urls": target_list if action_type == "post_url" else [],
        # How the interaction budget is split across several sources (targets, hashtags,
        # post URLs): balanced (default) / sequential / interleaved.
        "distribution": normalize_distribution(raw_config.get("distribution")),
        # WHICH post of a hashtag is worth opening — the profile filters above say who, among
        # its likers, deserves an interaction. This builder is a whitelist: without this entry
        # the operator's setting never reached the workflow, which then applied its catalogue
        # defaults (100-50000) whatever the page said. `None` = not specified, and the workflow
        # keeps those defaults; a bound at 0 means "no bound", as in the Feed workflow.
        "post_criteria": {
            "min_likes": int(post_criteria_config.get("minLikes", 0) or 0),
            "max_likes": int(post_criteria_config.get("maxLikes", 0) or 0),
        } if post_criteria_config else None,
        # Post URL — which population of the post to walk, and whether to act inside its
        # comment thread. This builder is a whitelist, so an unnamed key never reaches the
        # workflow; `None` here means "not specified", and the workflow keeps its default.
        "source_mode": raw_config.get("source_mode"),
        # Hashtag — ce que vaut CHAQUE post. Les trois se cumulent, avec un budget par
        # population et par post. `interaction_mode` reste accepte : c'est l'ancienne forme
        # exclusive, traduite par `resolve_interaction_plan` pour qu'un preset enregistre
        # continue de tourner. Whitelist : une cle absente ici n'atteint jamais le workflow.
        "interaction_mode": raw_config.get("interactionMode"),
        "engage_posts": raw_config.get("engagePosts"),
        "walk_likers": raw_config.get("walkLikers"),
        "walk_commenters": raw_config.get("walkCommenters"),
        "max_posts": raw_config.get("maxPosts"),
        "max_likers_per_post": raw_config.get("maxLikersPerPost"),
        "max_commenters_per_post": raw_config.get("maxCommentersPerPost"),
        "like_comments": raw_config.get("like_comments"),
        "reply_to_comments": raw_config.get("reply_to_comments"),
        "max_comment_likes": raw_config.get("max_comment_likes"),
        "max_comment_replies": raw_config.get("max_comment_replies"),
        "walk_profiles": raw_config.get("walk_profiles"),
        "interaction_type": interaction_type,
        "max_interactions": max_profiles,
        "like_posts": True,
        "min_likes_per_profile": min_likes_per_profile,
        "max_likes_per_profile": max_likes_per_profile,
        "probabilities": {
            "like_percentage": like_percentage,
            "follow_percentage": follow_percentage,
            "comment_percentage": comment_percentage,
            "story_percentage": story_percentage,
            "story_like_percentage": story_like_percentage,
        },
        "like_settings": {
            "enabled": like_percentage > 0,
            "like_carousels": True,
            "like_reels": True,
            "randomize_order": True,
            "methods": ["button_click", "double_tap"],
            "verify_like_success": True,
            "max_attempts_per_post": 2,
            "delay_between_attempts": 2,
        },
        "follow_settings": {
            "enabled": follow_percentage > 0,
            "unfollow_after_days": 3,
            "verify_follow_success": True,
        },
        "story_settings": {
            "enabled": story_percentage > 0,
            "watch_duration_range": [3, 8],
        },
        "story_like_settings": {
            "enabled": story_like_percentage > 0,
            "max_stories_per_user": 3,
            "like_probability": story_like_percentage / 100.0,
            "verify_like_success": True,
        },
        "comment_settings": {
            "enabled": comment_percentage > 0,
            "custom_comments": comments_config.get("customComments", []),
        },
        "scrolling": {
            "enabled": True,
            "max_scroll_attempts": 3,
            "scroll_delay": 1.5,
        },
    }

    if max_consecutive_known_usernames is not None:
        action_config["max_consecutive_known_usernames"] = max_consecutive_known_usernames
    if max_no_new_usernames_scrolls is not None:
        action_config["max_no_new_usernames_scrolls"] = max_no_new_usernames_scrolls

    # === Filtres profil — l'ACTION doit les porter, pas seulement built["filters"] ===
    #
    # Les runners target/hashtag/post_url reconstruisent leur config via
    # `FilterCriteria.from_action(action)` (cles PLATES sur l'action), et les chemins
    # notifications/feed lisent `action.get('filters')` (dict imbrique). Aucun des deux ne voit
    # jamais le `built["filters"]` top-level : sans ces cles, les filtres regles dans l'app
    # (min/max abonnes, min posts...) etaient silencieusement remplaces par les defauts du
    # dataclass, et les flags de relation etaient avales avec — verifie sur un run reel
    # (etat 'following' lu, profil quand meme traite).
    #
    # Regle bornes HAUTES : 0 = pas de limite (un "Max followers: 0" transmis litteralement
    # rejetterait tout profil ayant un seul abonne — meme garde que le mapper du scraping).
    action_filters: Dict[str, Any] = {
        "min_followers": int(filters.get("minFollowers", 50) or 0),
        "max_followers": int(filters.get("maxFollowers", 50000) or 0) or 100000,
        "min_posts": int(filters.get("minPosts", 5) or 0),
        "max_following": int(filters.get("maxFollowing", 7500) or 0) or 10000,
        "skip_follows_us": bool(filters.get("skipFollowsUs", False)),
        "skip_already_following": bool(filters.get("skipAlreadyFollowing", False)),
        # Revisit delays, in days, scoped to the account being automated (0 = never come
        # back). Absent -> RevisitPolicy defaults, so a standalone run is unchanged.
        "reinteraction_days": filters.get("reinteractionDays"),
        "refilter_days": filters.get("refilterDays"),
        # Private-zone escape. BOTH keys must travel: `allow_private` is what disarms the
        # mechanism (nothing rejected -> no zone to leave), and without it here the policy
        # would read the dataclass default and stay armed even when the operator accepts
        # private profiles. Absent -> PrivateStreakPolicy defaults, standalone unchanged.
        "allow_private": bool(filters.get("allowPrivate", False)),
        "max_consecutive_private_profiles": filters.get("maxConsecutivePrivateProfiles"),
    }
    action_config.update(action_filters)          # cles plates -> FilterCriteria.from_action
    action_config["filters"] = dict(action_filters)  # dict imbrique -> action.get('filters')

    return action_config


def build_instagram_automation_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the legacy CLI-compatible config consumed by Instagram automation."""
    target = raw_config.get("target", "")
    workflow_type = raw_config.get("workflowType")
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    session_config = raw_config.get("session", {})
    ai_config = raw_config.get("ai", {})
    decision_config = ai_config.get("decision") if isinstance(ai_config, dict) else {}
    decision_mode = (
        isinstance(decision_config, dict) and decision_config.get("mode") == "decide"
    )
    decision_capabilities = (
        decision_config.get("capabilities", {}) if decision_mode else {}
    )

    max_profiles = limits.get("maxProfiles", 20)
    min_likes_per_profile = limits.get("minLikesPerProfile", 1)
    max_likes_per_profile = limits.get("maxLikesPerProfile", 2)
    like_percentage = probabilities.get("like", 80)
    follow_percentage = probabilities.get("follow", 20)
    comment_percentage = probabilities.get("comment", 5)
    story_percentage = probabilities.get("watchStories", 15)
    story_like_percentage = probabilities.get("likeStories", 10)
    if decision_mode:
        # The intention sliders have no authority in decision mode. Convert the operator's
        # capability mask to 100/0 only for legacy execution settings/session ceilings; the
        # per-profile selection itself still comes exclusively from Electron's concrete plan.
        like_percentage = 100 if decision_capabilities.get("like") is True else 0
        follow_percentage = 100 if decision_capabilities.get("follow") is True else 0
        comment_percentage = 100 if decision_capabilities.get("comment") is True else 0
        story_percentage = 100 if decision_capabilities.get("watchStories") is True else 0
        story_like_percentage = 100 if decision_capabilities.get("likeStories") is True else 0
    min_followers = filters.get("minFollowers", 50)
    max_followers = filters.get("maxFollowers", 50000)
    min_posts = filters.get("minPosts", 5)
    max_followings = filters.get("maxFollowing", 7500)
    session_duration = session_config.get("durationMinutes", 60)
    # Explicit user delays are OPTIONAL now: when the UI sends a pacing profile instead
    # (behaviorPolicy) it omits minDelay/maxDelay, and the SessionManager derives the
    # between-actions delay from the profile. Only emit delay_between_actions when the
    # operator set explicit seconds (back-compat for pages that still send them).
    min_delay = session_config.get("minDelay")
    max_delay = session_config.get("maxDelay")
    max_consecutive_known_usernames = session_config.get("maxConsecutiveKnownUsernames")
    if max_consecutive_known_usernames is not None:
        max_consecutive_known_usernames = max(1, int(max_consecutive_known_usernames or 1))

    max_no_new_usernames_scrolls = session_config.get("maxNoNewUsernamesScrolls")
    if max_no_new_usernames_scrolls is not None:
        max_no_new_usernames_scrolls = max(1, int(max_no_new_usernames_scrolls or 1))

    target_list = [t.strip() for t in target.split(",") if t.strip()]
    primary_target = target_list[0] if target_list else target

    if workflow_type == "target_followers":
        interaction_type = "followers"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"
    elif workflow_type == "target_following":
        interaction_type = "following"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"
    elif workflow_type == "hashtags":
        interaction_type = "hashtag"
        action_type = "hashtag"
        session_workflow_type = "hashtag"
    elif workflow_type == "post_url":
        interaction_type = "post-likers"
        action_type = "post_url"
        session_workflow_type = "target_followers"
    elif workflow_type == "unfollow":
        interaction_type = "unfollow"
        action_type = "unfollow"
        session_workflow_type = "unfollow"
    elif workflow_type == "sync_following":
        interaction_type = "sync_following"
        action_type = "sync_following"
        session_workflow_type = "sync_following"
    elif workflow_type == "sync_followers_following":
        interaction_type = "sync_followers_following"
        action_type = "sync_followers_following"
        session_workflow_type = "sync_following"
    elif workflow_type == "feed":
        interaction_type = "feed"
        action_type = "feed"
        session_workflow_type = "feed"
    elif workflow_type == "notifications":
        # Reading the activity feed belongs to the notifications ENGAGEMENT bridge, which owns
        # the only implementation (and its persistence / dedup / app lifecycle). Falling through
        # to the default below would silently turn "read my notifications" into a FOLLOWER
        # interaction run, so this is a hard error instead.
        raise ValueError(
            "workflowType 'notifications' is served by notifications_bridge, not desktop_bridge"
        )
    elif workflow_type:
        # A present-but-unknown type is a caller bug (typo, or a new workflow whose
        # mapping was never added here). The old behaviour — defaulting to a follower
        # interaction run — executes the WRONG workflow on a real account.
        raise ValueError(
            f"Unknown workflowType {workflow_type!r} for desktop_bridge; "
            f"supported: {', '.join(SUPPORTED_WORKFLOW_TYPES)}"
        )
    else:
        # Absent type: documented standalone/CLI default, kept for back-compat with
        # configs that predate workflowType. The desktop app always sends one.
        logger.warning(
            "No workflowType in automation config; defaulting to interact_with_followers"
        )
        interaction_type = "followers"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"

    session_settings: Dict[str, Any] = {
        "workflow_type": session_workflow_type,
        "total_profiles_limit": max_profiles,
        "total_follows_limit": math.ceil(max_profiles * (follow_percentage / 100))
        if follow_percentage > 0
        else 0,
        "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_percentage / 100))
        if like_percentage > 0
        else 0,
        "session_duration_minutes": session_duration,
        "skip_initial_restart": True,
        "randomize_actions": True,
        "enable_screenshots": True,
        "screenshot_path": "screenshots",
    }

    # Only honour explicit user delays; otherwise the pacing profile drives the rhythm.
    if min_delay is not None or max_delay is not None:
        session_settings["delay_between_actions"] = {
            "min": min_delay if min_delay is not None else 5,
            "max": max_delay if max_delay is not None else 15,
        }

    if max_consecutive_known_usernames is not None:
        session_settings["max_consecutive_known_usernames"] = max_consecutive_known_usernames
    if max_no_new_usernames_scrolls is not None:
        session_settings["max_no_new_usernames_scrolls"] = max_no_new_usernames_scrolls

    built: Dict[str, Any] = {
        "filters": {
            "min_followers": min_followers,
            "max_followers": max_followers,
            "min_followings": 0,
            "max_followings": max_followings,
            "min_posts": min_posts,
            "privacy_relation": "public_and_private",
            "blacklist_words": [],
            # Relation deja existante — deux axes independants, opt-in (absent/False = comportement
            # inchange). Lus par `_relationship_skip_reason` juste apres l'extraction du profil.
            "skip_follows_us": bool(filters.get("skipFollowsUs", False)),
            "skip_already_following": bool(filters.get("skipAlreadyFollowing", False)),
        },
        "session_settings": session_settings,
        "actions": [
            _build_action_config(
                raw_config=raw_config,
                action_type=action_type,
                interaction_type=interaction_type,
                primary_target=primary_target,
                target_list=target_list,
                max_profiles=max_profiles,
                min_likes_per_profile=min_likes_per_profile,
                max_likes_per_profile=max_likes_per_profile,
                like_percentage=like_percentage,
                follow_percentage=follow_percentage,
                comment_percentage=comment_percentage,
                story_percentage=story_percentage,
                story_like_percentage=story_like_percentage,
                max_consecutive_known_usernames=max_consecutive_known_usernames,
                max_no_new_usernames_scrolls=max_no_new_usernames_scrolls,
            )
        ],
    }

    if decision_mode:
        # Defense in depth: the interaction engine can now identify decision mode even if the
        # premium hook/provider fails before depositing a response on profile_data. In that case
        # it executes an empty plan instead of silently falling back to probability rolls.
        built["actions"][0]["ai_decision_mode"] = "decide"
        built["actions"][0]["ai_decision_dry_run"] = bool(
            decision_config.get("dryRun", True)
        )
        built["actions"][0]["ai_decision_capabilities"] = dict(decision_capabilities)

    # Pass the pacing/behaviour profile through to the SessionManager (which reads
    # config["behaviorPolicy"] via parse_behavior_policy) so the rhythm selector works.
    behavior_policy = raw_config.get("behaviorPolicy")
    if behavior_policy is not None:
        built["behaviorPolicy"] = behavior_policy

    # Warmup guardrail caps, injected by the desktop app. The front computes them from the
    # account's age (private curve) and sends only NUMBERS; the public bot never sees the curve.
    # SessionManager enforces them: a floor on the between-actions delay (cadence) and a hard stop
    # when the day's budget is reached (defense in depth behind the front's launch gate). Absent
    # when the bot runs standalone -> no enforcement, behaviour unchanged. 0 = no cap on that axis.
    warmup = raw_config.get("warmupPolicy")
    if isinstance(warmup, dict):
        session_settings["warmup_policy"] = {
            "max_actions_per_day": int(warmup.get("maxActionsPerDay", 0) or 0),
            "max_follows_per_day": int(warmup.get("maxFollowsPerDay", 0) or 0),
            "max_comments_per_day": int(warmup.get("maxCommentsPerDay", 0) or 0),
            "min_action_gap_seconds": float(warmup.get("minActionGapSeconds", 0) or 0),
            "max_actions_per_session": int(warmup.get("maxActionsPerSession", 0) or 0),
        }

    return built


def build_instagram_session_config_event(
    raw_config: Dict[str, Any],
    *,
    ai_enabled: bool = False,
) -> Dict[str, Any]:
    """Build the structured session_config event payload emitted by the bridge."""
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    session_config = raw_config.get("session", {})
    ai_config = raw_config.get("ai", {})

    session_payload: Dict[str, Any] = {
        "durationMinutes": session_config.get("durationMinutes", 60),
    }
    # Faithful to the rhythm model: only advertise explicit delays. When the run is
    # rhythm-driven (no minDelay/maxDelay) the analyzer shows "Rythme" instead of a
    # fake 5-15s window and skips delay-violation checks against bounds that don't apply.
    min_delay = session_config.get("minDelay")
    max_delay = session_config.get("maxDelay")
    if min_delay is not None:
        session_payload["minDelay"] = min_delay
    if max_delay is not None:
        session_payload["maxDelay"] = max_delay
    if session_config.get("maxConsecutiveKnownUsernames") is not None:
        session_payload["maxConsecutiveKnownUsernames"] = session_config.get(
            "maxConsecutiveKnownUsernames"
        )
    if session_config.get("maxNoNewUsernamesScrolls") is not None:
        session_payload["maxNoNewUsernamesScrolls"] = session_config.get(
            "maxNoNewUsernamesScrolls"
        )

    payload: Dict[str, Any] = {
        "deviceId": raw_config.get("deviceId"),
        "workflowType": raw_config.get("workflowType"),
        "target": raw_config.get("target"),
        "limits": {
            "maxProfiles": limits.get("maxProfiles", 20),
            "maxLikesPerProfile": limits.get("maxLikesPerProfile", 2),
        },
        "probabilities": {
            "like": probabilities.get("like", 80),
            "follow": probabilities.get("follow", 20),
            "comment": probabilities.get("comment", 5),
            "watchStories": probabilities.get("watchStories", 15),
            "likeStories": probabilities.get("likeStories", 10),
        },
        "filters": {
            "minFollowers": filters.get("minFollowers", 50),
            "maxFollowers": filters.get("maxFollowers", 50000),
            "minPosts": filters.get("minPosts", 5),
            "maxFollowing": filters.get("maxFollowing", 7500),
        },
        "session": session_payload,
    }

    # Surface the pacing/rhythm profile so the UI can show "Rythme : prudent/équilibré/rapide".
    behavior_policy = raw_config.get("behaviorPolicy")
    if behavior_policy is not None:
        payload["behaviorPolicy"] = behavior_policy

    if ai_enabled:
        payload["ai"] = {
            "enabled": True,
            "smartComments": ai_config.get("smartComments", False),
            "profileAnalysis": ai_config.get("profileAnalysis", False),
            "postAnalysis": ai_config.get("postAnalysis", False),
        }
        # Opt-in relevance gating (front-owned settings) — pass through verbatim so a
        # scheduled run gates exactly like a manual one. Absent → engine passthrough.
        relevance_gating = ai_config.get("relevanceGating") or ai_config.get("relevance_gating")
        if isinstance(relevance_gating, dict):
            payload["ai"]["relevanceGating"] = relevance_gating
        decision = ai_config.get("decision")
        if isinstance(decision, dict):
            payload["ai"]["decision"] = decision

    return payload
