"""Why a bridge failed or refused to run: the codes its `error` line carries, and their sentences.

Distinct from why a run ended (`stop_reasons.py`): a stop reason closes a session the run opened; an
error code says why a bridge could not run, or broke off (a phone without network, a device that
does not connect, a payload refused, a crash). It travels in the `error_code` field of the `error`
line (`shared.ERROR_EVENT`).

Each code names the key of its sentence in the app's translations (namespace `sessionLive`, French
and English): the app generates its table from here (`BRIDGE_ERROR_PHRASE_KEYS`), and its gate
(`npm run i18n:keys`) refuses a key missing from a language. One cause has one code: two codes that
shared a sentence were synonyms and are renamed (`device_connection_failed` of the publication is
`DEVICE_CONNECTION_FAILED`, `LAUNCH_FAILED` of the persona analysis is `INSTAGRAM_LAUNCH_FAILED`), and
a code says its cause (`LICENSE_SETUP_FAILED`, sent when the run's base did not open, is
`DATABASE_SETUP_FAILED`). `tests/unit/contract/test_workflow_contract_error_codes.py` holds the
catalogue to the codes the bridges and the core emit, read from the source: a code emitted and not
listed, or listed and emitted nowhere, is red, and so is a sentence shared by two codes.

Some codes are not failures: a bridge refused to run, on purpose, on a state of the phone it checked
before touching anything, or on a key it lacks (`BRIDGE_REFUSAL_CODES`). The run did its job; the app says the sentence and
files no crash report for it. Every other code is a failure worth a report, a payload refused
included (the app wrote that payload).
"""

from __future__ import annotations

from typing import Mapping, Tuple

from .schema import OneOf

#: Code -> the key of its sentence in the app (`sessionLive`), one sentence per code.
BRIDGE_ERROR_PHRASES: Mapping[str, str] = {
    # The start of a run: the phone, its network, the app.
    "NETWORK_UNREACHABLE": "errorNetworkUnreachable",
    "NETWORK_RESET_FAILED": "errorNetworkResetFailed",
    "DEVICE_CONNECTION_FAILED": "errorDeviceConnectionFailed",
    "DEVICE_CONNECTION_TIMEOUT": "errorDeviceConnectionTimeout",
    # The run's base did not open (`configure_db_service`).
    "DATABASE_SETUP_FAILED": "errorDatabaseSetupFailed",
    "ATX_AGENT_FAILED": "errorAtxAgentFailed",
    "INSTAGRAM_NOT_INSTALLED": "errorInstagramNotInstalled",
    "INSTAGRAM_LAUNCH_FAILED": "errorInstagramLaunchFailed",
    # During a run.
    "ATX_AGENT_CRASHED": "errorAtxAgentCrashed",
    "WORKFLOW_TIMEOUT": "errorWorkflowTimeout",
    "WORKFLOW_ERROR": "errorWorkflowError",
    "UNHANDLED_EXCEPTION": "errorUnhandledException",
    # A module the run needs did not import (`crash_hooks.exception_event`), wherever the import ran.
    "PYTHON_IMPORT_ERROR": "errorPythonImport",
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
    # A DM reply in the conversation, waiting to be sent (no network): Instagram sends it by itself
    # when the network is back; sent again, it would be there twice (`dm_send`).
    "DM_SEND_PENDING": "errorDmSendPending",
    # A reading of the DM inbox, or of its requests folder, that read nothing, and never says « 0
    # conversation » for it (`dm_read`, `workflows/dm/session.py`): the inbox is not on screen; its
    # list shows no row, no header and no empty page (not loaded); Instagram says it did not load it;
    # the requests folder did not open.
    "DM_INBOX_NOT_SHOWN": "errorDmInboxNotShown",
    "DM_LIST_NOT_LOADED": "errorDmListNotLoaded",
    "DM_LIST_LOAD_FAILED": "errorDmListLoadFailed",
    "DM_REQUESTS_NOT_OPENED": "errorDmRequestsNotOpened",
    # A run that asks for the AI (`WorkflowContract.ai_request`) and has no usable key (`MissingAIKeyError`).
    "missing_ai_key": "errorMissingAiKey",
    # The launcher (`bridges/launcher.py`): it was named no bridge, or one its manifest does not list
    # (the app and the bot are not of one version); its manifest does not read (a broken install).
    "UNKNOWN_BRIDGE": "errorUnknownBridge",
    "BRIDGE_MANIFEST_UNREADABLE": "errorBridgeManifestUnreadable",
    # The entry of every bridge (`entrypoint.run_bridge_main`): no config file, or one that does not
    # read as a JSON object.
    "MISSING_CONFIG": "errorBridgeConfigMissing",
    "CONFIG_ERROR": "errorBridgeConfigUnreadable",
    # The tools of the Cartography Lab (selector bench, workflow bench).
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

#: The expected refusals: the phone has no network (the network door), the app the run needs is not
#: on the phone, the run asks for the AI and no key is saved (the same code the app's launch gate gives).
#: The remedy is the operator's, not a fix of the bot; the app's reading of a dead bridge
#: (`crashErrorCode.ts`) files no crash report for an exit on one of them. Not here: what may be the
#: bot's own fault (a device that does not connect, an IP rotation that failed, Instagram that does
#: not start), and what is decided mid-run (a publication Instagram refuses).
BRIDGE_REFUSAL_CODES: Tuple[str, ...] = (
    "NETWORK_UNREACHABLE",
    "INSTAGRAM_NOT_INSTALLED",
    "APP_NOT_INSTALLED",
    "missing_ai_key",
)

#: The codes, as the named closed set the `error` line refers to.
BRIDGE_ERROR_CODE = OneOf(
    tuple(BRIDGE_ERROR_PHRASES),
    name="BridgeErrorCode",
    doc="Why a bridge failed or refused to run (`error_code` of its `error` line).",
)

__all__ = ["BRIDGE_ERROR_CODE", "BRIDGE_ERROR_PHRASES", "BRIDGE_REFUSAL_CODES"]
