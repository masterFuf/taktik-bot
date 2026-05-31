# Changelog

All notable changes to TAKTIK Instagram Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- `taktik/core` architecture cleanup continued in small verified lots: shared device boundaries were clarified, Instagram database ownership was tightened, and Instagram/TikTok selector trees were reorganized by real UI scope (`shell`, `surfaces`, `flows`, `support`).
- Legacy top-level selector shim files were removed for Instagram and TikTok once internal imports had been migrated to the scoped owners.
- `taktik/core/compat` now scopes its selector compatibility framework under `compat/selectors/**`; internal bridges import the scoped owners directly while the old top-level modules stay as compatibility shims.
- `taktik/core/clone` now centralizes official package names and clone prefixes in `clone/package_map.py` so detector, proxy, and selector patching share the same source of truth.
- The Instagram human behavior recorder now lives under `taktik/core/social_media/instagram/recorder/**`; `taktik/core/recorder` remains only as a compatibility facade for legacy script imports.
- Runtime hygiene continued in `taktik/core/config` and `taktik/core/security`: `APIEndpointManager` now keeps the legacy `get_primary_endpoint()` alias expected by historical Instagram code, and dormant security helpers no longer print to stdout.
- Instagram media capture now lives under `taktik/core/social_media/instagram/media/**`; `taktik/core/media/**` remains as a compatibility facade, and proxy asset resolution now targets the repo-level `scripts/` directory explicitly.
- `taktik/core/app/email/gmail/workflows/account.py` no longer imports the bridge IPC directly; Gmail bridges and TikTok signup now inject a notifier, keeping `core` decoupled from `bridges.common.*`.
- `taktik/core/agent` now has a documented target as a cross-platform runtime kernel: the Front remains the premium planner, while the Bot is the local plan executor; `TaktikAgentWorkflow` is now treated as a legacy Instagram-first scenario on that path.
- `taktik/core/agent` now exposes first runtime-kernel contracts (`AgentPlan`, `PlanStep`, `WorkflowInvocation`, `AgentEvent`) and no longer imports `bridges.common.ai_service` directly; the Instagram bridge now injects the AI provider factory.
- The Instagram scraping workflow no longer builds its own bridge IPC and AI provider inside `taktik/core`; the bridge and CLI now inject the runtime dependencies instead.
- `taktik/core/agent` now also exposes a first `WorkflowRegistry` and `AgentPlanExecutor`, so plan execution can start moving out of scenario-specific workflows without a big-bang rewrite.
- TikTok management workflows (`login`, `logout`, `signup`) no longer instantiate the bridge IPC inside `taktik/core`; the TikTok account bridge now injects the notifier instead.
- The TikTok publish workflow now follows the same runtime rule: it keeps a standalone fallback notifier, but `tiktok_publish_bridge.py` injects the live bridge notifier instead of letting `taktik/core` create it directly.
- The OpenRouter `AIService` provider now lives under `taktik/core/app/ai/providers/openrouter.py`; bridge imports use the app owner while `bridges/common/ai_service.py` remains as a compatibility shim.
- The agent runtime can now read `workflows.manifest.json` through `taktik/core/agent/io/manifest.py` and expose canonical `platform.family.workflow` ids for future `AgentPlan` execution.
- The agent runtime now exposes JSON-safe `AgentPlan` parsing and serialization through `taktik/core/agent/io/plan.py`, with optional manifest validation for workflow ids.
- `TaktikAgentWorkflow` now accepts optional `agent_plan` / `agentPlan` payloads and exposes the parsed plan in `AgentContext` without changing the existing Instagram-first scenario execution or adding a new stdout event.
- `taktik/core/agent/kernel/runtime.py` now provides the first parse-and-execute facade for injected workflow registries, keeping real Android workflow binding outside the kernel for now.
- `taktik/core/agent/io/events.py` now serializes `AgentEvent` instances into JSON-safe payloads for future bridge integration.
- The Bot core refactor trackers now distinguish completed agent kernel extraction from the remaining work of binding real workflow handlers.
- `clone/**` and `compat/**` now have an explicit structural audit: `clone` owns package/clone runtime, `compat/selectors` owns selector versioning/tracing, and top-level compat modules remain legacy shims only.
- `taktik/core/agent` is now physically split into scoped owners: `kernel/`, `io/`, `decision/`, and `scenarios/`; the package root is kept as a public facade through `__init__.py`.
- `taktik/core/ai` moved to `taktik/core/app/ai` without a root compatibility shim; bridge, CLI and agent imports now target the app AI owner directly.
- The target taxonomy now documents the conservative physical state of `taktik/core`: root families stay stable for now, while runtime packages are cleaned internally before any future `app/` / `runtime/` move.
- The obsolete `taktik/core/device` static compatibility package was removed; remaining bridges, debug scripts and `taktik.core.DeviceManager` now use `taktik/core/shared/device/manager.py` directly.
- Shared action helpers moved from `taktik/core/shared/utils/action_utils.py` to `taktik/core/shared/actions/utils.py`; the generic `shared/utils` package was removed.
- The unused Instagram `utils` package was removed; the remaining logger setup moved to `taktik/core/social_media/instagram/observability/logging.py`.
- Instagram automation workflow helpers moved from `workflows/helpers` to `workflows/support`, leaving the old generic helper package removed.
- The obsolete `DatabaseHelpers` Instagram business shim was removed; runtime code must import the canonical `taktik.core.database` services directly.
- TikTok publish services moved from flat `services/publish_*.py` modules into the scoped `services/publish/**` package.
- TikTok followers services moved from flat `services/followers_*.py` and `services/known_profiles_stop_policy.py` modules into the scoped `services/followers/**` package.
- TikTok profile username extraction moved from flat `services/profile_username.py` into the scoped `services/profile/username.py` service.
- TikTok navigation reset moved from flat `services/navigation_reset.py` into the scoped `services/navigation/reset.py` service.
- TikTok app lifecycle and package resolution services moved from flat `services/app_control.py` and `services/package_resolver.py` into `services/runtime/**`.
- `taktik/core/config` and `taktik/core/security` now scope their runtime implementation under `config/runtime/**` and `security/protection/**`, while keeping legacy import paths stable.
- `taktik/core/recorder` is now reduced to a package-level compatibility facade; the Instagram recorder implementation remains under `social_media/instagram/recorder/**`.
- `taktik/core/clone` is now split by ownership into `detection/`, `packages/`, `device/`, and `selectors/`, with the package root kept as the public facade.
- `taktik/core/compat` no longer keeps top-level selector shim modules; `compat/selectors/**` is the only internal owner and `compat/__init__.py` is the public facade.
- `taktik/core/app/email/gmail` is split into `workflows/` and `ui/` so Gmail workflow logic and selectors no longer share the provider package root.
- `taktik/core/email` moved to `taktik/core/app/email` without a root compatibility shim; Gmail, YouTube and TikTok signup imports now target the app email owner directly.
- Sent DM duplicate-prevention SQL moved out of `bridges/common/database.py` into `taktik/core/database/repositories/messaging/SentDMRepository`; the bridge module now remains a compatibility facade for existing Instagram/TikTok imports.
- `taktik/core/media` is now reduced to package-level compatibility facades; the Instagram media capture/proxy implementation remains under `social_media/instagram/media/**`.
- Database model compatibility objects now live in `taktik/core/database/models/instagram_profile.py` instead of the historical duplicate path `models/models.py`.
- Instagram core IPC emission no longer imports desktop bridges directly; `bridges/instagram/base.py` injects its adapter into `IPCEmitter`, keeping core workflows standalone-safe.
- Runtime root migration started without compatibility shims: `taktik/core/config` and `taktik/core/security` were moved to `taktik/core/app/config` and `taktik/core/app/security`, and internal imports now use the new owners directly.
- The obsolete `taktik/core/recorder` facade was removed; scripts and tests now import the Instagram recorder owner directly from `social_media/instagram/recorder`.
- The obsolete `taktik/core/media` facade was removed; desktop media capture and setup scripts now import the Instagram media owner directly from `social_media/instagram/media`.
- TikTok session lifecycle SQL moved from the monolithic `repositories/tiktok/tiktok_repository.py` body into `repositories/tiktok/session/session_repository.py`, while `TikTokRepository` remains the public facade.
- TikTok daily stats SQL moved from the monolithic `repositories/tiktok/tiktok_repository.py` body into `repositories/tiktok/stats/stats_repository.py`.
- TikTok interaction-history SQL moved from the monolithic `repositories/tiktok/tiktok_repository.py` body into `repositories/tiktok/interaction/interaction_repository.py`.
- TikTok filtered-profile SQL moved from the monolithic `repositories/tiktok/tiktok_repository.py` body into `repositories/tiktok/filtering/filtered_profile_repository.py`.
- TikTok account/profile SQL moved into `repositories/tiktok/account/**` and `repositories/tiktok/profile/**`; `tiktok_repository.py` is now only the public facade.
- The TikTok Followers workflow repository adapter moved from flat `repositories/tiktok/followers_repository.py` into `repositories/tiktok/followers/followers_repository.py` and now uses the explicit `TikTokFollowersRepository` name.
- The TikTok publish workflow now imports specialized publish selector catalogs directly instead of the public `PUBLISH_SELECTORS` compatibility aggregate.
- TikTok services now import navigation, popup, followers and profile selectors from scoped `shell/**` / `surfaces/**` owners instead of the top-level selector aggregate.
- TikTok atomic/profile actions now import scoped selector owners directly instead of the top-level selector aggregate.
- The TikTok Followers workflow now imports selector catalogs from scoped `surfaces/**` owners instead of the top-level selector aggregate.
- TikTok shared workflow internals, scraping and unfollow workflows now import selector catalogs from scoped owners instead of the top-level selector aggregate.
- TikTok workflow notifier context handling is now centralized under `social_media/tiktok/workflows/runtime/notifier.py`; management and publish workflows keep injected bridge notifiers while standalone fallbacks remain local to Bot core.
- Instagram auth workflows now import auth and popup selectors from scoped `ui/selectors/shell/**` owners instead of the top-level selector aggregate.
- Instagram atomic text actions now get text-input and detection selectors from scoped `ui/selectors/shell/**` owners; unused aggregate imports were removed from the text mixins.
- Instagram atomic navigation actions now import navigation, detection and profile selectors from scoped shell/surface owners instead of the top-level selector aggregate.
- Instagram atomic detection actions now import screen-state, profile, post and story selectors from scoped shell/surface owners instead of the top-level selector aggregate.
- Instagram atomic scroll actions now import screen-state and post-comment selectors from scoped owners, with unused aggregate imports removed from scroll mixins.
- Instagram atomic interaction actions now import button, navigation, popup, post, profile and story selectors from scoped owners instead of the top-level selector aggregate.
- Instagram shared workflow common helpers now import popup and post selectors from scoped owners instead of the top-level selector aggregate.
- Instagram workflow UI support helpers now use scoped popup, screen-state and likers selector owners directly, without lazy imports from the top-level aggregate.
- Instagram scraping and post-scraping workflows now import post/profile/comment selector catalogs from scoped surface owners instead of the top-level selector aggregate.
- Instagram management DM/content workflows now import direct-message, navigation, profile and content-creation selectors from scoped owners instead of the top-level selector aggregate.
- Instagram core automation, base business actions and recorder now import their selector catalogs from scoped shell/surface owners instead of the top-level selector aggregate.
- Instagram business actions and workflows now import like/comment/messaging/feed/hashtag/followers/notification/unfollow selectors from scoped owners instead of the top-level selector aggregate.
- Instagram human behavior recorder no longer keeps screen/content XPath catalogs inline; missing recorder probes now consume scoped selector owners for feed, reels, stories, profile, DM, comments and notifications.
- `AGENTS.md` now requires a full-file re-read whenever a file is touched during refactor, so obvious architecture-rule violations are caught beyond the edited lines.
- Stale TikTok publish/navigation documentation and workflow comments now point at scoped selector owners instead of removed top-level selector files.
- Instagram workflow UI helpers now read Follow/Suivre button labels from the scoped profile selector catalog instead of hardcoding UI text in workflow support code.
- Instagram post scraping helpers now read the comments empty-state selector from `POST_COMMENTS_SELECTORS` instead of keeping the resource id inline.
- Instagram comment actions now use `POST_COMMENTS_SELECTORS` directly, including popup defocus and IME-back selectors that were previously inline in the action.
- Instagram deep-qualify scraping now reads the profile header container selector from `PROFILE_SELECTORS` instead of keeping the resource id inline.

### Notes
- Public compatibility aggregates such as `POST_SELECTORS`, `VIDEO_SELECTORS`, and `PUBLISH_SELECTORS` are intentionally kept for now pending broader manual workflow validation; internal publish workflow code now uses the specialized publish catalogs directly.
- The `sent_dms` table keeps its historical Python-side `(account_id, recipient_username, platform)` dedup behavior for bridge workflows; no shared Electron schema migration was introduced in this lot.

### Fixed
- TikTok local schema now creates the `tiktok_scraped_profiles` junction table directly, matching the repository that links scraped TikTok profiles to scraping sessions.

---

## [1.2.1] - 2025-12-23

### Changed
- Updated version alignment with TAKTIK Desktop app to 1.2.1
- Synchronized version numbering across bot and desktop application

---

## [1.2.0] - 2025-12-20

### Added
- **Cold DM Workflow**: Automated cold DM campaigns to targeted users
  - Send personalized messages to scraped profiles
  - Private profile detection and handling
  - Configurable message templates with variable substitution
  - Integration with desktop app for campaign management

- **DM Auto Reply**: Automatic response system for incoming DMs
  - AI-powered response generation
  - Customizable triggers and response templates
  - Group chat detection and handling
  - Smart navigation optimization

- **Screen Mirroring**: Real-time device screen mirroring in desktop app
  - Live view of Android device screen
  - Touch interaction support
  - Performance optimized for smooth streaming

- **AI Content Generation**: Generate Instagram content with AI
  - Post caption generation
  - Image generation with fal.ai integration
  - Multiple AI model support (Claude, GPT-4, Gemini)

- **Local Database Migration**: SQLite-based local data storage
  - All Instagram data stored locally in %APPDATA%/taktik-desktop/taktik-data.db
  - Improved privacy and performance
  - Offline capability for data access
  - Remote API only receives aggregated stats

- **New Workflows**:
  - Feed interaction workflow
  - Notifications workflow
  - Unfollow from following list
  - Business account management

- **Enhanced Session Management**:
  - Session finalization with stop reason tracking
  - Scraping session statistics
  - Enriched profile scraping with on-the-fly details
  - Better session timing metrics

### Improved
- Business workflows (feed/notifications) optimization
- Atomic actions and selectors refinement
- DM auto-reply with group detection
- Navigation reliability and performance
- Workflow runner plumbing

### Technical
- New `cold_dm_bridge.py` for cold DM campaigns
- Enhanced `dm_bridge.py` with auto-reply capabilities
- Local database schema with better-sqlite3 (Electron) and sqlite3 (Python)
- Desktop bridge extended for new workflow types and stats
- Scraping session tracking in database

---

## [1.1.9] - 2025-12-15

### Fixed
- UTF-8 encoding issues in file operations
- Permission errors on Windows systems
- Log file encoding set to UTF-8

---

## [1.1.8] - 2025-12-12

### Added
- Feed interaction workflow
- Notifications workflow
- Unfollow from following list workflow

---

## [1.1.7] - 2025-12-11

### Changed
- Migrated to local SQLite database for Instagram data storage
- Remote API now only receives aggregated statistics

---

## [1.1.6] - 2025-12-10

### Added
- **DM Bridge**: Unified Python bridge for reading and sending Instagram DMs
  - Read conversations with full message history (sent + received)
  - Send messages with human-like typing simulation
  - Emoji and special character support
  - Integration with TAKTIK Desktop app

- **Media Capture Service**: Intercept Instagram CDN media using mitmproxy
  - Capture stories, reels, and posts media URLs
  - Real-time media interception during browsing
  - Export captured media for analysis

- **Frida SSL Bypass**: Certificate pinning bypass for Instagram Android
  - `frida_ssl_bypass.js` script for SSL unpinning
  - Works with mitmproxy for HTTPS traffic inspection
  - Compatible with Instagram app versions 300+

- **Enhanced Followers Tracking**: Insomniac-style position verification
  - Loop detection to prevent infinite scrolling
  - Position-based duplicate detection
  - Improved extraction reliability on large accounts

- **Multi-Target Diagnostics**: Better debugging for follower extraction
  - Detailed logging of extraction progress
  - Target switching diagnostics
  - Performance metrics per target

### Improved
- **Target Workflow**: More reliable follower extraction with better termination conditions
- **DM Reading**: Now captures both sent and received messages for full conversation context
- **Human-like Behavior**: Optimized typing delays (faster but still natural)

### Technical
- Unified `dm_bridge.py` replaces `dm_bridge_desktop.py` and `dm_send_bridge.py`
- New `media_capture/` service module with mitmproxy integration
- Frida scripts in `frida/` directory for SSL bypass

---

## [1.1.5] - 2025-12-05

### Added
- **Post URL Scraping Workflow**: Extract and interact with users who liked specific posts
- Various bug fixes and stability improvements

---

## [1.1.3] - 2025-12-02

### Refactored
- **Centralized number parsing**: All number parsing logic now uses `parse_number_from_text` from `extractors.py`
  - Eliminated code duplication in `like.py`, `utils.py`, and `profile.py`
  - Fixed follower count parsing for large accounts with space before K/M suffix (e.g., "166 K" → 166,000)
  - All parsing improvements now apply automatically across the entire codebase

- **Centralized problematic page selectors**: Created `ProblematicPageSelectors` class in `selectors.py`
  - Moved hardcoded selectors from `problematic_page.py` to centralized location
  - Improved maintainability and consistency of UI selectors
  - All problematic page detection and closing now uses centralized selectors

### Fixed
- **Follower count parsing for large accounts**: Fixed parsing of follower counts with space before K/M suffix (e.g., "166 K" for 166,000 followers)
  - Instagram displays large numbers with a space before the suffix on some devices/locales
  - Previously, "166 K" was incorrectly parsed as 166 instead of 166,000
  - This caused premature termination of follower scraping on accounts with thousands of followers

---

## [1.1.1] - 2025-11-26

### Added
- **Multi-target follower extraction**: Support for extracting followers from multiple target profiles in a single session
  - CLI now accepts comma-separated usernames (e.g., `user1,user2,user3`)
  - Automatic switching between targets when extraction limits are reached
  - Accumulated follower list across all targets for interaction
  
- **Intelligent end-of-list detection**: Prevents infinite scrolling on profiles with limited followers
  - Uses profile's total follower count to detect when ~95% of followers have been seen
  - Automatically switches to next target when current profile is exhausted
  - Significantly reduces wasted scrolling time
  
- **Automatic popup detection and closure**: Enhanced problematic page detector
  - New pattern for "Mute notifications" popup (`mute_notifications_popup`)
  - Improved `swipe_down_handle` method with dynamic element targeting
  - Resolution-agnostic implementation using element bounds instead of fixed coordinates
  - Automatic detection and closure after profile navigation

### Improved
- **Navigation reliability**: Integrated problematic page detector into navigation flow
  - Automatic popup closure after each profile navigation
  - Reduced navigation failures due to blocking popups
  
- **Follower extraction efficiency**: 
  - Smarter extraction limits based on profile follower count
  - Better handling of profiles with few followers
  - Reduced unnecessary scrolling attempts

### Fixed
- Infinite scrolling issue on profiles with limited followers
- Navigation failures caused by "Mute notifications" popup
- Follower extraction stopping prematurely when switching targets

### Technical Details
- Enhanced `ProblematicPageDetector` with resolution-independent element targeting
- Modified `NavigationActions` to include automatic popup detection
- Updated `interact_with_target_followers` to support multi-target workflow
- Improved `_extract_followers_with_scroll` with intelligent termination conditions

---

## [1.1.0] - Previous Release

### Features
- Core Instagram automation functionality
- Follower/following interaction workflows
- Hashtag-based targeting
- Post URL interaction
- Session management and limits
- Database integration for tracking processed profiles
- License system integration

---

## Version History

- **1.1.6** (2025-12-10): DM Bridge, Media Capture, Frida SSL Bypass, Enhanced Tracking
- **1.1.5** (2025-12-05): Post URL scraping workflow
- **1.1.3** (2025-12-02): Centralized number parsing and UI selectors
- **1.1.2** (2025-12-02): Fix follower count parsing for large accounts (K/M with space)
- **1.1.1** (2025-11-26): Multi-target support, intelligent scrolling, automatic popup handling
- **1.1.0**: Core automation features and workflows
