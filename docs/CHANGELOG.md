# Changelog

All notable changes to TAKTIK Instagram Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- `bridges/tiktok` started moving away from a flat module list: internal dispatcher runners for For You, Search/Hashtag, Followers and DM read/send now live under `bridges/tiktok/workflows/{automation,engagement}/`, while public Electron entrypoints remain at the platform root.
- `bridges/common` started the same capability-based cleanup: bridge network reset helpers now live under `bridges/common/device/network.py` instead of the flat common root.
- Bridge keyboard typing and count parsing helpers are now scoped under `bridges/common/input/keyboard.py` and `bridges/common/parsing/counts.py`; the flat `keyboard.py` and `utils.py` common modules were removed.
- Bridge DB facade helpers now live under `bridges/common/persistence/database.py`, leaving SQLite ownership in `taktik/core/database/**` while removing another flat common module.
- The unused `bridges/common/ai_service.py` compatibility shim was removed; bridge code imports AI providers from `taktik/core/app/ai/**` directly.
- Bridge device connection and app lifecycle helpers now live under `bridges/common/device/{connection,app_manager}.py`; the flat `connection.py` and `app_manager.py` common modules were removed.
- Bridge runtime helpers now live under `bridges/common/runtime/{bootstrap,ipc,bridge_base,signal_handler}.py`, leaving `bridges/common` as a package facade instead of a flat module bucket.
- Instagram Smart Comment bridge implementation moved under `bridges/instagram/engagement/smart_comment.py`; `smart_comment_bridge.py` is now only the public Electron entrypoint wrapper.
- Instagram DM and Cold DM bridge implementations moved under `bridges/instagram/engagement/{dm,cold_dm}.py`; `dm_bridge.py` and `cold_dm_bridge.py` remain public Electron entrypoint wrappers.
- Instagram account bridge implementation moved under `bridges/instagram/account/account.py`; `account_bridge.py` remains the public Electron entrypoint wrapper.
- Instagram scraping bridge implementation moved under `bridges/instagram/scraping/scraping.py`; `scraping_bridge.py` remains the public Electron entrypoint wrapper.
- Instagram Persona Analysis bridge implementation moved under `bridges/instagram/analysis/persona.py`; `persona_analysis_bridge.py` remains the public Electron entrypoint wrapper, and its post caption/comment probes now come from scoped post selector catalogs.
- Instagram Taktik Agent bridge implementation moved under `bridges/instagram/agent/taktik_agent.py`; `taktik_agent_bridge.py` remains the public Electron entrypoint wrapper while the Agent kernel stays under `taktik/core/agent`.
- Instagram desktop automation bridge implementation moved under `bridges/instagram/automation/desktop.py`; `desktop_bridge.py` remains the public Electron entrypoint wrapper.
- TikTok account bridge implementation moved under `bridges/tiktok/account/account.py`; `tiktok_account_bridge.py` remains the public Electron entrypoint wrapper.
- TikTok publish bridge implementation moved under `bridges/tiktok/publish/publish.py`; `tiktok_publish_bridge.py` remains the public Electron entrypoint wrapper.
- Public bridge entrypoint wrappers now bootstrap the Bot root into `sys.path` before importing scoped implementations, preserving direct script launches from Electron and standalone usage.
- TikTok scraping bridge implementation moved under `bridges/tiktok/scraping/scraping.py`; `scraping_bridge.py` remains the public Electron entrypoint wrapper and the TikTok dispatcher imports the scoped owner directly.
- TikTok DM outreach bridge implementation moved under `bridges/tiktok/engagement/dm_outreach.py`; `dm_outreach_bridge.py` remains the public Electron entrypoint wrapper.
- TikTok unfollow bridge implementation moved under `bridges/tiktok/automation/unfollow.py`; `tiktok_unfollow_bridge.py` remains the public Electron entrypoint wrapper.
- TikTok workflow dispatcher implementation moved under `bridges/tiktok/workflows/dispatcher.py`; `tiktok_bridge.py` remains the public Electron entrypoint wrapper.
- YouTube bridge implementations moved under scoped owners: `account/account.py`, `publish/upload.py`, `diagnostics/action_test.py`, and `workflows/dispatcher.py`; root bridge files remain public entrypoint wrappers.
- Gmail account bridge implementation moved under `bridges/gmail/account/account.py`; `gmail_account_bridge.py` remains the public Electron entrypoint wrapper.
- Threads workflow dispatcher implementation moved under `bridges/threads/workflows/dispatcher.py`; `threads_bridge.py` remains the public Electron entrypoint wrapper.
- Compatibility diagnostic bridge implementations moved under `bridges/compat/diagnostics/**`; root compat bridge files remain public Electron entrypoint wrappers.
- Bridge entrypoints v2 removed the root wrapper layer: dev and packaged launches now both route through `bridge_name + launcher` (`python bridges/launcher.py <bridge_name>` or `taktik_launcher.exe <bridge_name>`), while `bridges.manifest.json`, PyInstaller build scripts and Electron path resolution point directly to scoped implementation modules.
- `taktik_launcher.spec` now derives bridge hidden imports from `bridges.manifest.json` and repo-local paths instead of hardcoded wrapper modules and machine-specific paths.
- Instagram desktop automation bridge cleanup started: debug commands now live under `bridges/instagram/diagnostics/debug.py`, CLI/stdin config loading under `bridges/instagram/automation/runtime/input.py`, and optional media capture lifecycle under `bridges/instagram/automation/runtime/media_capture.py`, leaving `automation/desktop.py` focused on session orchestration.
- Instagram desktop workflow execution now lives in `bridges/instagram/automation/runtime/workflow.py`, with AI service setup in `automation/runtime/ai.py`; `automation/desktop.py` delegates workflow preparation, session config events, AI hook installation and final stats emission to the runner.
- Instagram desktop bridge runtime lifecycle now lives in `bridges/instagram/automation/runtime/session.py`: SQLite setup, device connection, app launch, optional network reset and app cleanup are no longer embedded in `automation/desktop.py`.
- Instagram desktop bridge support modules are now grouped under `bridges/instagram/automation/runtime/**`, aligning the Instagram automation tree with the TikTok owner pattern instead of leaving support files flat beside the entrypoint.
- Instagram DM bridge CLI/read/send command handling moved under `bridges/instagram/engagement/runtime/dm_commands.py`; `engagement/dm.py` now keeps the DM UI automation class and delegates command dispatch to the engagement runtime support owner.
- Instagram DM inbox and conversation navigation moved under `bridges/instagram/engagement/runtime/dm_navigation.py`, keeping `engagement/dm.py` focused on message send/read automation.
- Instagram DM conversation reading and message extraction moved under `bridges/instagram/engagement/runtime/dm_reader.py`; `engagement/dm.py` now owns only DM send/composer automation plus the launcher `main()`.
- Instagram Cold DM config-file entrypoint handling moved under `bridges/instagram/engagement/runtime/cold_dm_commands.py`; `engagement/cold_dm.py` now delegates CLI/config orchestration to the engagement runtime support owner.
- Instagram Cold DM sent-DM duplicate/persistence calls moved under `bridges/instagram/engagement/runtime/cold_dm_persistence.py`, keeping bridge DB access behind the bridge persistence adapter.
- Instagram Cold DM OpenRouter message generation moved under `bridges/instagram/engagement/runtime/cold_dm_ai.py`; the bridge workflow now calls the runtime adapter instead of owning HTTP AI generation.
- Instagram Cold DM search/profile/home navigation moved under `bridges/instagram/engagement/runtime/cold_dm_navigation.py`; `engagement/cold_dm.py` now keeps message sending and campaign orchestration instead of owning every UI step.
- Instagram Cold DM composer/send-button/invite-state handling moved under `bridges/instagram/engagement/runtime/cold_dm_sender.py`; the bridge workflow no longer owns keyboard input details.
- Instagram Smart Comment config loading and `scrape`/`reply_all` CLI routing moved under `bridges/instagram/engagement/runtime/smart_comment_commands.py`; the bridge implementation keeps the workflow class and preserves JSON stdout errors through the launcher.
- Instagram Smart Comment data models (`ScrapedComment`, `TargetProfile`, `PostContext`) moved under `bridges/instagram/engagement/runtime/smart_comment_models.py`, reducing model ownership noise in the workflow bridge file.
- Instagram Smart Comment Litho dumpsys comment parsing moved under `bridges/instagram/engagement/runtime/smart_comment_parsing.py`; count parsing now uses `bridges/common/parsing/counts.py` directly from the workflow.
- Instagram Smart Comment post screenshot capture moved under `bridges/instagram/engagement/runtime/smart_comment_media.py`, keeping temporary media file ownership out of the workflow bridge file.
- Instagram Smart Comment target profile navigation, profile scraping and first-post opening moved under `bridges/instagram/engagement/runtime/smart_comment_target.py`, leaving the main bridge focused on post/comment/reply phases.
- Instagram Smart Comment comment opening, sorting, visible-comment extraction, dumpsys scraping, comment scrolling and reply-thread expansion moved under `bridges/instagram/engagement/runtime/smart_comment_comments.py`.
- Instagram Smart Comment reply finding, keyboard typing, send-button handling, reply batching and reply progress events moved under `bridges/instagram/engagement/runtime/smart_comment_reply.py`.
- Instagram Smart Comment post context extraction (caption expansion, author/date/stat parsing and post URL clipboard capture) moved under `bridges/instagram/engagement/runtime/smart_comment_post_context.py`.
- Instagram Smart Comment exact-post navigation, post fingerprint verification and profile fallback search moved under `bridges/instagram/engagement/runtime/smart_comment_navigation.py`.
- Instagram Smart Comment scrape orchestration and scrape result serialization moved under `bridges/instagram/engagement/runtime/smart_comment_scrape.py`; `engagement/smart_comment.py` is now a thin bridge composition/root entrypoint.
- Instagram Persona Analysis config loading, DB bootstrap, device connection and final JSON emission moved under `bridges/instagram/analysis/runtime/persona_commands.py`; `analysis/persona.py` now keeps the persona workflow class and delegates CLI handling to the analysis runtime owner.
- Instagram Persona Analysis post comment scraping moved under `bridges/instagram/analysis/runtime/persona_comments.py`, keeping post comment selector traversal outside the main persona bridge workflow.
- Instagram Persona Analysis profile screenshot capture moved under `bridges/instagram/analysis/runtime/persona_media.py`, preserving the base64 JPEG data URI output while moving media capture out of the workflow class.
- TikTok Account bridge support moved under `bridges/tiktok/account/runtime/**`: CLI/config loading, DB/device/app preparation, clone selector patching and login/logout/register dispatch are no longer embedded in `account/account.py`.
- TikTok bridge base runtime capabilities moved under `bridges/tiktok/runtime/**`: platform IPC helpers, app/profile startup and video callback wiring now have explicit owners while `base.py` stays a thin facade.
- TikTok bridge internals now import runtime capabilities from their direct owners instead of depending on the `bridges/tiktok/base.py` facade.
- TikTok Followers bridge runner support moved under `bridges/tiktok/workflows/automation/runtime/**`: target planning, FollowersConfig mapping, stats aggregation and live callbacks are no longer embedded in `followers.py`.
- Instagram bridge base runtime capabilities moved under `bridges/instagram/runtime/**`: Instagram IPC helpers and the clone-aware bridge base now have explicit owners while `base.py` remains the stable facade registered with core IPC emitter.
- Instagram bridge internals now import runtime capabilities from their direct owners; `base.py` is retained as a stable compatibility facade for external/smoke imports.
- Threads dispatcher runners moved under `bridges/threads/workflows/runtime/**`; `workflows/dispatcher.py` now focuses on config loading, workflow routing and cleanup.
- Bridge app package/activity metadata moved under `bridges/common/device/apps.py`; `AppService` now owns lifecycle behavior while the catalog has its own device owner.
- Instagram Smart Comment comments runtime now consumes `POST_COMMENTS_SELECTORS` for comment UI signatures instead of hardcoding comment button/title/sort/list/reply-expand selectors inline.
- Instagram Smart Comment comments runtime was split into focused extraction and comment-list navigation mixins, leaving `smart_comment_comments.py` as the comments phase orchestrator.
- Instagram Smart Comment reply runtime now consumes `POST_COMMENTS_SELECTORS` for reply input/send/list/title signatures instead of hardcoding them inline.
- Instagram Smart Comment reply runtime was split into focused finder and sender mixins, keeping target Reply discovery, composer/send handling, and batch orchestration under separate owners.
- Instagram DM inbox navigation now reads direct-tab, inbox header, bottom-tab and recommendation probes from the scoped direct-message selector catalog instead of keeping resource ids and visible labels inline.
- Instagram DM message sending moved under `engagement/runtime/dm_sender.py`; the bridge entrypoint now composes sender/reader/navigation mixins and the composer/send probes live in `DM_SELECTORS`.
- Instagram DM command orchestration now reuses `DM_SELECTORS` for inbox presence, Instagram-open probes and conversation back navigation instead of embedding resource ids in the bridge command layer.
- Instagram DM conversation reading now consumes scoped direct-message selectors for headers, composer presence, text/reel messages and group-detection probes while preserving the existing `conversation` JSON payload.
- Instagram Smart Comment post navigation now uses scoped post/comment selector catalogs for landing verification and comment-title probes instead of hardcoded post action resource ids.
- Instagram Smart Comment post-context extraction now uses scoped post selectors for caption expansion, author/media probes and share/copy-link UI while preserving the `post_context` event payload.
- Instagram Account bridge session lifecycle now lives under `account/runtime/session.py`, leaving `account/account.py` focused on validation and workflow dispatch while preserving JSON stdout messages.
- Instagram Account bridge CLI/config loading moved under `account/runtime/commands.py`, keeping the public launcher behavior and usage JSON unchanged.
- Instagram Persona Analysis post scraping now lives under `analysis/runtime/persona_posts.py`, leaving `analysis/persona.py` focused on launch/profile orchestration and final result assembly.
- Instagram Persona Analysis profile navigation and metadata copy now live under `analysis/runtime/persona_profile.py`, keeping target-profile resolution out of the bridge entrypoint.
- Instagram Scraping bridge workflow config mapping moved under `scraping/runtime/config.py`, keeping the entrypoint focused on CLI, DB/device setup, workflow execution and JSON output.
- Instagram Scraping bridge CLI/config loading moved under `scraping/runtime/commands.py`, preserving the existing JSON errors for missing config, invalid config and missing `deviceId`.
- Instagram Scraping bridge OpenRouter factory moved under `scraping/runtime/ai.py`, keeping AI provider creation as an injected bridge runtime concern.
- Instagram Scraping workflow execution moved under `scraping/runtime/workflow.py`, keeping runtime logging, IPC/AI injection and result normalization outside the entrypoint.
- Instagram Scraping DB/device lifecycle moved under `scraping/runtime/session.py`, leaving the entrypoint to compose config, session, workflow and JSON output.
- Instagram Cold DM recipient filtering moved under `engagement/runtime/cold_dm_recipients.py`, keeping already-sent checks out of the send-loop entrypoint.
- Instagram Cold DM message selection moved under `engagement/runtime/cold_dm_messages.py`, isolating AI-vs-random choice from the send loop while preserving retry/reset behavior.
- Instagram Cold DM progress JSON emission moved under `engagement/runtime/cold_dm_progress.py`, keeping stdout event formatting out of the send-loop logic.
- Instagram Cold DM inter-message delay handling moved under `engagement/runtime/cold_dm_timing.py`, preserving the historical wait condition against the full filtered recipient list.
- Instagram Cold DM send-result handling moved under `engagement/runtime/cold_dm_results.py`, isolating counter updates, success records and invite-sent handling from the loop.
- Instagram Desktop bridge config validation and target display formatting moved under `automation/runtime/validation.py`, keeping the entrypoint focused on lifecycle orchestration.
- Instagram Desktop bridge signal handler registration moved under `automation/runtime/signals.py`, preserving the existing shutdown status event and `running` flag behavior.
- Instagram Desktop bridge `debugMode` dispatch moved under `automation/runtime/entrypoint.py`, leaving `main()` focused on config loading and JSON error handling.
- Instagram Desktop workflow final-stats and error emitters moved under `automation/runtime/events.py`, keeping stdout event formatting out of the workflow runner.
- Instagram Desktop `session_config` event emission now lives under `automation/runtime/events.py`, preserving the core-built payload while reducing runner responsibilities.
- Instagram Taktik Agent bridge OpenRouter factory moved under `agent/runtime/ai.py`, preserving provider injection into the core Agent workflow.
- Instagram Taktik Agent bridge CLI/config loading moved under `agent/runtime/commands.py`, preserving JSON errors for missing config, invalid config and missing `deviceId`.
- Instagram Taktik Agent bridge DB setup and device connection moved under `agent/runtime/session.py`, preserving the existing JSON connection failure.
- Instagram Taktik Agent bridge stdin `stop` listener moved under `agent/runtime/stop_listener.py`, keeping command-listening bridge runtime separate from workflow orchestration.
- Instagram Taktik Agent bridge app launch and workflow runner moved under `agent/runtime/workflow.py`, while the core Agent orchestration remains under `taktik/core/agent`.
- Instagram Cold DM search navigation moved under `engagement/runtime/cold_dm_search.py`, leaving `cold_dm_navigation.py` focused on profile, back and home navigation.
- Instagram runtime IPC stats helpers moved under `runtime/ipc_stats.py`, while `runtime/ipc.py` keeps the same public exports and stdout JSON event names.
- Instagram runtime IPC live interaction events moved under `runtime/ipc_interaction_events.py`, while `runtime/ipc.py` remains the injected public adapter for core workflows.
- Instagram runtime IPC scraping/discovery events moved under `runtime/ipc_scraping_events.py`, leaving `runtime/ipc.py` as a thin public adapter facade.
- Instagram Persona Analysis bridge runtime class moved under `analysis/runtime/persona_bridge.py`; `analysis/persona.py` remains the public manifest entrypoint.
- Instagram scraping bridge orchestration moved under `scraping/runtime/runner.py`; `scraping/scraping.py` remains the public manifest entrypoint.
- Instagram account bridge runtime class moved under `account/runtime/bridge.py`; `account/account.py` remains the public manifest entrypoint.
- Instagram DM bridge runtime class moved under `engagement/runtime/dm_bridge.py`; `engagement/dm.py` remains the public manifest entrypoint.
- Instagram Smart Comment bridge runtime class moved under `engagement/runtime/smart_comment_bridge.py`; reply/scrape title defocus now uses the post comments selector catalog instead of inline resource IDs.
- Instagram Cold DM bridge workflow class moved under `engagement/runtime/cold_dm_workflow.py`; `engagement/cold_dm.py` remains the public manifest entrypoint.
- Instagram Taktik Agent bridge runtime class moved under `agent/runtime/bridge.py`; the core Agent orchestration remains under `taktik/core/agent` and still receives IPC/AI by injection.
- Instagram desktop automation bridge runtime class moved under `automation/runtime/bridge.py`; `automation/desktop.py` remains the public manifest entrypoint.
- TikTok account bridge runtime class moved under `account/runtime/bridge.py`; `account/account.py` remains the public manifest entrypoint.
- TikTok publish bridge CLI and runtime class moved under `publish/runtime/**`; `publish/publish.py` remains the public manifest entrypoint.
- Instagram Cold DM navigation and sender runtime now consume existing navigation/profile/direct-message selector catalogs instead of embedding search, private-profile, message-button and composer probes inline.
- Instagram Smart Comment target helpers now use scoped profile/post selectors for fallback username extraction and post/reel landing checks.
- Instagram Smart Comment comments runtime now reads remaining Android class probes from `POST_COMMENTS_SELECTORS` instead of embedding `Button`/`ViewGroup` class names inline.
- Instagram DM inbox reset/top-position logic moved to `engagement/runtime/dm_inbox_reset.py`, leaving `dm_navigation.py` focused on reaching the inbox and opening conversations.
- Instagram DM text/reel message collection moved to `engagement/runtime/dm_message_extraction.py`, leaving `dm_reader.py` focused on conversation traversal and JSON emission.
- Instagram DM conversation lookup/opening moved to `engagement/runtime/dm_conversation_navigation.py`, leaving `dm_navigation.py` focused on entering the inbox.
- Instagram Smart Comment post URL retrieval moved to `engagement/runtime/smart_comment_post_url.py`, leaving post-context extraction focused on caption, date and stats.
- Instagram Smart Comment post stats extraction moved to `engagement/runtime/smart_comment_post_stats.py`, leaving post-context extraction focused on caption, date, author and event emission.
- Instagram Smart Comment post fingerprint verification moved to `engagement/runtime/smart_comment_post_fingerprint.py`, leaving post navigation focused on URL/profile/comment traversal.
- Instagram DM conversation state handling moved to `engagement/runtime/dm_conversation_state.py`, leaving `dm_reader.py` focused on traversal and JSON conversation events.
- Instagram DM session positioning helpers (`ensure_dm_inbox`, `return_to_inbox`) moved to `engagement/runtime/dm_session.py`, leaving `dm_commands.py` focused on CLI dispatch and JSON responses.
- Instagram Account bridge workflow runners now live under `account/runtime/workflows.py`, leaving `account/account.py` focused on config validation, DB/device/app setup and workflow dispatch.
- `taktik/core` architecture cleanup continued in small verified lots: shared device boundaries were clarified, Instagram database ownership was tightened, and Instagram/TikTok selector trees were reorganized by real UI scope (`shell`, `surfaces`, `flows`, `support`).
- Legacy top-level selector shim files were removed for Instagram and TikTok once internal imports had been migrated to the scoped owners.
- `taktik/core/compat` now scopes its selector compatibility framework under `compat/selectors/**`; internal bridges import the scoped owners directly while the old top-level modules stay as compatibility shims.
- `taktik/core/clone` now centralizes official package names and clone prefixes in `clone/package_map.py` so detector, proxy, and selector patching share the same source of truth.
- TikTok runtime package resolution now also consumes shared clone package variants from `clone/package_map.py`, removing the publish-runtime dependency on `tiktok/core/manager.py`.
- TikTok publish now delegates package restart/lifecycle to `services/runtime/app_control.py` instead of keeping app-start fallback logic inside the upload workflow.
- TikTok package resolution now accepts an injected command runner, matching the runtime app-control testability pattern.
- TikTok publish now exposes an injectable Agent `WorkflowRegistry` handler for `tiktok.standalone.upload_post`, allowing the agent runtime to execute the real upload workflow when a caller provides device/notifier dependencies.
- YouTube publish now exposes the same injectable Agent handler pattern for `youtube.publish.upload_post`, including bridge-compatible parameter normalization and Shorts title trimming.
- TikTok Followers now exposes an injectable Agent handler for `tiktok.automation.followers`; the handler owns one target only, normalizes bridge-compatible parameters into `FollowersConfig`, and leaves multi-target orchestration to composed Agent plan steps.
- TikTok For You now exposes an injectable Agent handler for `tiktok.automation.for_you`, with bridge-compatible video feed parameters and callback forwarding kept outside bridge startup concerns.
- TikTok Search/Hashtag/Target now expose injectable Agent handlers for `tiktok.automation.search`, `tiktok.automation.hashtag`, and `tiktok.automation.target`; each handler invocation owns one query and leaves multi-query orchestration to Agent plan composition.
- TikTok Agent workflow handlers now share local adapter primitives from `actions/business/workflows/_internal/agent_runtime.py`, avoiding duplicated payload coercion/callback wiring without creating a root-level helper bucket.
- TikTok Unfollow now exposes an injectable Agent handler for `tiktok.standalone.tiktok_unfollow`, preserving the bridge `skipFriends` default while normalizing it into `UnfollowConfig.include_friends`.
- TikTok Scraping now exposes injectable Agent handlers for `tiktok.automation.scraping` and `tiktok.standalone.tiktok_scraping`; DB persistence stays outside the handler through an optional injected `profile_sink`.
- TikTok DM Read/Send now expose injectable Agent handlers for `tiktok.automation.dm_read` and `tiktok.automation.dm_send`, while startup, live IPC and outreach DB dedup remain outside those handlers.
- TikTok cold DM outreach business logic moved from `bridges/tiktok/dm_outreach_bridge.py` into `social_media/tiktok/actions/business/workflows/dm/outreach.py`; the bridge now injects stdout IPC and sent-DM duplicate persistence.
- TikTok cold DM outreach now exposes an injectable Agent handler for `tiktok.standalone.tiktok_dm_outreach`, reusing the same notifier and sent-DM dedup injection points.
- TikTok account workflows now expose injectable Agent handlers for `tiktok.account.login`, `tiktok.account.logout`, and `tiktok.account.register`; bridge/device launch and package patching remain external startup concerns.
- Gmail account workflows now expose injectable Agent handlers for `gmail.account.login`, `gmail.account.logout`, `gmail.account.read_otp`, and `gmail.account.scan_accounts`; account DB persistence/unpersistence is optional and injected.
- YouTube account login/logout logic now lives under `social_media/youtube/workflows/account/**`; `youtube_account_bridge.py` stays a thin adapter for DB bootstrap, device connection, force-stop cleanup and stdout JSON.
- YouTube account workflows now expose injectable Agent handlers for `youtube.account.login` and `youtube.account.logout`, with notifier and Google-account persistence dependencies provided by the caller.
- Instagram account workflows now expose injectable Agent handlers for `instagram.account.login`, `instagram.account.logout`, and `instagram.account.register`; bridge/device launch stays outside the handler.
- Instagram scraping workflows now expose injectable Agent handlers for `instagram.scraping.target`, `instagram.scraping.hashtag`, and `instagram.scraping.post_url`, with bridge-compatible config normalization and injected `device_manager`/AI provider dependencies.
- Instagram automation config normalization now lives under `social_media/instagram/workflows/core/config_builder.py`; `desktop_bridge.py` delegates workflow config and structured `session_config` payload mapping to it so future Agent handlers can reuse bridge-compatible normalization without owning bridge startup/runtime.
- Instagram automation AI hook installation now lives under `social_media/instagram/workflows/core/ai_hooks.py`; the desktop bridge injects AI service, device, language and log callback, while post crop selectors are centralized in `POST_DETAIL_SELECTORS`.
- Instagram automation runtime setup now lives under `social_media/instagram/workflows/core/runtime_setup.py`; package propagation, active clone package, selector version overrides and language optimization are applied through injected bridge/runtime dependencies.
- Instagram automation workflows now expose injectable Agent handlers for `instagram.automation.*`; the handler reuses the extracted config/runtime/AI setup and still leaves device connection, app launch, network reset and media capture to the caller/bridge.
- Threads search/feed workflows now accept an injected startup tuple, preserving bridge startup by default while allowing future Agent handlers to execute without opening device connections themselves.
- Threads automation workflows now expose injectable Agent handlers for `threads.automation.follow`, `threads.automation.target`, and `threads.automation.feed`; the caller must provide startup/device runtime instead of the handler opening a connection.
- `AGENTS.md` now documents where real Agent `WorkflowRegistry` handlers belong: next to their platform workflow owner, with injected device/notifier dependencies and no bridge ownership.
- The Instagram human behavior recorder now lives under `taktik/core/social_media/instagram/recorder/**`; `taktik/core/recorder` remains only as a compatibility facade for legacy script imports.
- Runtime hygiene continued in `taktik/core/config` and `taktik/core/security`: `APIEndpointManager` now keeps the legacy `get_primary_endpoint()` alias expected by historical Instagram code, and dormant security helpers no longer print to stdout.
- Instagram media capture now lives under `taktik/core/social_media/instagram/media/**`; `taktik/core/media/**` remains as a compatibility facade, and proxy asset resolution now targets the repo-level `scripts/` directory explicitly.
- `taktik/core/app/email/gmail/workflows/account.py` no longer imports the bridge IPC directly; Gmail bridges and TikTok signup now inject a notifier, keeping `core` decoupled from `bridges.common.*`.
- `taktik/core/agent` now has a documented target as a cross-platform runtime kernel: the Front remains the premium planner, while the Bot is the local plan executor; `TaktikAgentWorkflow` is now treated as a legacy Instagram-first scenario on that path.
- `taktik/core/agent` now exposes first runtime-kernel contracts (`AgentPlan`, `PlanStep`, `WorkflowInvocation`, `AgentEvent`) and no longer imports `bridges.common.ai_service` directly; the Instagram bridge now injects the AI provider factory.
- `taktik/core/agent/kernel` now separates data contracts from injected runtime ports: plan/event dataclasses stay in `contracts.py`, while AI service protocols live in `ports.py`.
- The Instagram scraping workflow no longer builds its own bridge IPC and AI provider inside `taktik/core`; the bridge and CLI now inject the runtime dependencies instead.
- `taktik/core/agent` now also exposes a first `WorkflowRegistry` and `AgentPlanExecutor`, so plan execution can start moving out of scenario-specific workflows without a big-bang rewrite.
- The agent runtime can now preflight missing workflow handlers for a valid `AgentPlan`, and the executor rejects incomplete plans before emitting events or running partial workflow side effects.
- Missing agent workflow handlers now raise a structured `MissingWorkflowHandlersError` with a JSON-safe payload for future bridge integration.
- TikTok management workflows (`login`, `logout`, `signup`) no longer instantiate the bridge IPC inside `taktik/core`; the TikTok account bridge now injects the notifier instead.
- The TikTok publish workflow now follows the same runtime rule: it keeps a standalone fallback notifier, but `tiktok_publish_bridge.py` injects the live bridge notifier instead of letting `taktik/core` create it directly.
- The OpenRouter `AIService` provider now lives under `taktik/core/app/ai/providers/openrouter.py`; bridge imports use the app owner directly and the old `bridges/common/ai_service.py` shim has since been removed.
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
- Instagram post-scraping comment sort options now use the scoped post-comments selector catalog instead of building a `content-desc` XPath inline in the workflow.
- TikTok DM atomic actions now use scoped inbox selector builders for notification section titles and conversation username fallbacks instead of composing XPath strings in the action.
- Instagram search navigation now uses scoped navigation selector builders for profile result rows and hashtag result/confirmation selectors instead of composing XPath strings inside the action.
- Instagram comment scrolling now uses a scoped post-comments selector builder for the comments list instead of composing a `resource-id` XPath in the scroll action.
- Instagram scraping commenter-list strategy now reads its button-node scan selector from `POST_COMMENTS_SELECTORS` instead of keeping raw XPath in the strategy.
- TikTok video author profile-picture cropping now uses the scoped creator selector catalog for package-specific avatar resource ids instead of hardcoding package names in the detector.
- TikTok video like-count detection now gets generic Like-video content-description fallbacks from `VIDEO_ENGAGEMENT_SELECTORS` instead of composing them inline in `video_detector.py`.
- TikTok search profile navigation now uses the scoped search selector catalog for username result fallbacks instead of composing XPath strings in the action.
- TikTok profile extraction now reads website/verified/private visible probes from the scoped profile selector catalog instead of hardcoding raw uiautomator2 query strings.
- TikTok profile extraction now reads the bio button fallback selector from `PROFILE_SELECTORS` instead of hardcoding the uiautomator2 class selector.
- TikTok popup slow fallback now reuses the scoped popup selector catalog for video option bottom sheets, matching the fast-path detector.
- Instagram workflow watchdog UI dump signatures now live under the scoped selector support catalog instead of inline in `ui/watchdog.py`.
- Instagram problematic-page detector now reads Android permission allow-button fallbacks from `PROBLEMATIC_PAGE_SELECTORS` instead of keeping selector dictionaries inline.
- Instagram simple unfollow workflow now reads following-tab, following-button and confirm-button visible probes from the scoped unfollow flow selector catalog.
- Instagram unfollow following/follower sync mixins now use scoped unfollow selector builders for active-package follow-list resource ids and non-follower category XPath probes.
- Instagram core automation, base business actions and recorder now import their selector catalogs from scoped shell/surface owners instead of the top-level selector aggregate.
- Instagram business actions and workflows now import like/comment/messaging/feed/hashtag/followers/notification/unfollow selectors from scoped owners instead of the top-level selector aggregate.
- Instagram human behavior recorder no longer keeps screen/content XPath catalogs inline; missing recorder probes now consume scoped selector owners for feed, reels, stories, profile, DM, comments and notifications.
- `scripts/audit_selector_hardcodes.py` now blocks new inline Android UI selectors in Instagram/TikTok runtime code while making the remaining legacy selector debt explicit through an allowlist.
- The selector hardcode audit now distinguishes exact non-runtime signatures, such as parser regexes and synthetic compatibility probes, from real runtime selector debt.
- `AGENTS.md` now requires a full-file re-read whenever a file is touched during refactor, so obvious architecture-rule violations are caught beyond the edited lines.
- Stale TikTok publish/navigation documentation and workflow comments now point at scoped selector owners instead of removed top-level selector files.
- Instagram workflow UI helpers now read Follow/Suivre button labels from the scoped profile selector catalog instead of hardcoding UI text in workflow support code.
- Instagram post scraping helpers now read the comments empty-state selector from `POST_COMMENTS_SELECTORS` instead of keeping the resource id inline.
- Instagram post scraping stats/engagement extraction now reads generic button/view-group scan selectors and caption layout selector from `POST_DETAIL_SELECTORS` instead of keeping raw XPath in workflow code.
- Instagram comment actions now use `POST_COMMENTS_SELECTORS` directly, including popup defocus and IME-back selectors that were previously inline in the action.
- Instagram deep-qualify scraping now reads the profile header container selector from `PROFILE_SELECTORS` instead of keeping the resource id inline.
- Instagram login screen/result/popup helpers now read profile-tile, use-another-profile, save-info and Not-now selectors from `AUTH_SELECTORS` instead of keeping inline XPath lists.
- Instagram credential filling now reads autofill and password-only account selectors from `AUTH_SELECTORS` instead of keeping XPath probes inline.
- Instagram login screen debug logging now reads its clickable-visible element probe from `AUTH_SELECTORS` instead of keeping the XPath inline.
- TikTok popup actions now read the follow-friends close description from `POPUP_SELECTORS` instead of hardcoding the uiautomator2 description fallback.
- Instagram profile extraction now reuses `PROFILE_SELECTORS.profile_header_container` for About-account recovery instead of keeping the profile header XPath inline.
- Instagram profile count extraction now reads followers/following/posts resource ids and text probes from `PROFILE_SELECTORS` instead of passing raw UI labels from the extractor.
- Instagram profile count extraction now builds resource-id/text/content-desc fallback XPath through `PROFILE_SELECTORS`, keeping selector patterns out of the extractor.
- Instagram content publishing helpers now read POST/REEL/STORY type labels from `CONTENT_CREATION_SELECTORS` instead of hardcoding them in the workflow helper.
- Instagram content publishing helpers no longer keep the dead first `_handle_reel_draft_modal` definition that was overwritten by the later catalog-driven implementation.
- Instagram content publishing helpers now read popup, caption, location, publish and story button labels from `CONTENT_CREATION_SELECTORS`.
- Instagram content publishing helpers now read the edit-video detection regex from `CONTENT_CREATION_SELECTORS` instead of keeping the UI signature inline.
- Instagram content publishing helpers now read gallery container, location field/result and keyboard-window uiautomator fallbacks from `CONTENT_CREATION_SELECTORS`, further shrinking the selector hardcode audit allowlist.
- Instagram content hashtag navigation now builds its fallback result selectors through `CONTENT_CREATION_SELECTORS` instead of composing XPath in the action.
- Instagram DM management helpers now read direct-tab, conversation-back, send-button and profile-message uiautomator fallbacks from `DM_SELECTORS` / `PROFILE_SELECTORS`.
- Instagram DM reply/outreach/navigation helpers now also read edit-text/text-view class fallbacks and dynamic username/send-button uiautomator selectors from `DM_SELECTORS`, reducing the selector hardcode audit allowlist.

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
