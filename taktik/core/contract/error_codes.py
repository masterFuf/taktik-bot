"""Why a bridge failed or refused to run: the codes its `error` line carries, and their sentences.

Distinct from why a run ended (`stop_reasons.py`): a stop reason closes a session the run opened; an
error code says why a bridge could not run, or broke off (a phone without network, a device that
does not connect, a payload refused, a crash). It travels in the `error_code` field of the `error`
line (`shared.ERROR_EVENT`).

Each code names the key of its sentence in the app's translations (namespace `sessionLive`, French
and English): the app generates its table from here (`BRIDGE_ERROR_PHRASE_KEYS`), and its gate
(`npm run i18n:keys`) refuses a key missing from a language. The values are the codes the bot emits
today, none renamed; `tests/unit/contract/test_workflow_contract_error_codes.py` holds the catalogue
to the codes the bridges and the core emit, read from the source: a code emitted and not listed, or
listed and emitted nowhere, is red.
"""

from __future__ import annotations

from typing import Mapping

from .schema import OneOf

#: Code -> the key of its sentence in the app (`sessionLive`). Several codes may share a sentence.
BRIDGE_ERROR_PHRASES: Mapping[str, str] = {
    # The start of a run: the phone, its network, the app.
    "NETWORK_UNREACHABLE": "errorNetworkUnreachable",
    "NETWORK_RESET_FAILED": "errorNetworkResetFailed",
    "DEVICE_CONNECTION_FAILED": "errorDeviceConnectionFailed",
    "DEVICE_CONNECTION_TIMEOUT": "errorDeviceConnectionTimeout",
    # The Instagram publication says it in lower case (`bridges/instagram/publish/bridge.py`).
    "device_connection_failed": "errorDeviceConnectionFailed",
    # Sent by the Instagram automation when its database setup fails, under this historical name.
    "LICENSE_SETUP_FAILED": "errorLicenseSetupFailed",
    "ATX_AGENT_FAILED": "errorAtxAgentFailed",
    "INSTAGRAM_NOT_INSTALLED": "errorInstagramNotInstalled",
    "INSTAGRAM_LAUNCH_FAILED": "errorInstagramLaunchFailed",
    # The persona analysis says the same failure under a shorter name.
    "LAUNCH_FAILED": "errorInstagramLaunchFailed",
    # During a run.
    "ATX_AGENT_CRASHED": "errorAtxAgentCrashed",
    "WORKFLOW_TIMEOUT": "errorWorkflowTimeout",
    "WORKFLOW_ERROR": "errorWorkflowError",
    "UNHANDLED_EXCEPTION": "errorUnhandledException",
    # Threads.
    "threads.no_query": "errorThreadsNoQuery",
    "threads.unknown_workflow": "errorThreadsUnknownWorkflow",
    "threads.workflow_crash": "errorThreadsWorkflowCrash",
    # The Instagram publication, by the step that failed (`InstagramPostWorkflow._error`).
    "no_media": "errorPublishNoMedia",
    "file_not_found": "errorPublishFileNotFound",
    "push_failed": "errorPublishPushFailed",
    "gallery_item_not_found": "errorPublishGalleryItemNotFound",
    "create_not_found": "errorPublishCreateNotFound",
    "composer_not_reached": "errorPublishComposerNotReached",
    "caption_fill_failed": "errorPublishCaptionFillFailed",
    "share_not_found": "errorPublishShareNotFound",
    "action_blocked": "errorPublishActionBlocked",
    "publish_not_committed": "errorPublishNotCommitted",
    "story_tray_not_found": "errorPublishStoryTrayNotFound",
    "permission_prompt_unanswered": "errorPublishPermissionPromptUnanswered",
    "information_window_unanswered": "errorPublishInformationWindowUnanswered",
    # The check of a DM written by an AI (`ai_dm_check_bridge`).
    "AI_DM_CHECK_INPUT": "errorAiDmCheckInput",
    # The tools of the Cartography Lab (selector bench, workflow bench).
    "MISSING_CONFIG": "errorBridgeConfigMissing",
    "CONFIG_ERROR": "errorBridgeConfigUnreadable",
    "MISSING_DEVICE": "errorLabMissingDevice",
    "MISSING_TARGET": "errorLabMissingTarget",
    "CONNECTION_ERROR": "errorLabConnection",
    "REGISTRY_INIT_ERROR": "errorLabRegistryInit",
    "NO_SELECTORS": "errorLabNoSelectors",
    "AUTOMATION_INIT_ERROR": "errorLabAutomationInit",
    "APP_NOT_INSTALLED": "errorLabAppNotInstalled",
    "APP_LAUNCH_FAILED": "errorLabAppLaunchFailed",
    # The schema door of the database (`schema_bridge`).
    "SCHEMA_USAGE": "errorSchemaUsage",
    "SCHEMA_DB_PATH_MISMATCH": "errorSchemaDbPathMismatch",
    "SCHEMA_REFUSED": "errorSchemaRefused",
    "SCHEMA_MIGRATION_FAILED": "errorSchemaMigrationFailed",
}

#: The codes, as the named closed set the `error` line refers to.
BRIDGE_ERROR_CODE = OneOf(
    tuple(BRIDGE_ERROR_PHRASES),
    name="BridgeErrorCode",
    doc="Why a bridge failed or refused to run (`error_code` of its `error` line).",
)

__all__ = ["BRIDGE_ERROR_CODE", "BRIDGE_ERROR_PHRASES"]
