"""The diagnostic tools the app runs outside the workflow manifest: the lines of their stdout it reads.

- the workflow bench (`workflow_test_bridge`, the Lab's "Workflow test"), read by the compat handler;
- the selector bench (`selector_test_bridge`), read by the same handler;
- the Lab's persistent action session (`action_session_bridge`), read by
  `CartographyActionSessionService`;
- the debug tooling of the Instagram bridge (`desktop_bridge` with `debugMode`), read by
  `DesktopDebugBridgeService`.

No workflow id, no settings: what these tools read from their file is theirs (`ToolContract`).
The workflow bench drives the production launcher, whose own lines (the Instagram automation's)
reach its stdout too; the bench reads only the ones declared here.
"""

from __future__ import annotations

from .schema import Event, Field, ListOf, MapOf, OneOf, Shape, ToolContract
from .shared import ERROR_EVENT, LOG_EVENT, STATUS_EVENT, STEP_METRIC_EVENT

# ------------------------------------------------------------------------------ workflow bench

#: `ipc.send("step", ...)`: the bench's own stages (connect, launch, init, overrides, run, report).
BENCH_STEP_EVENT = Event("step", doc="A stage of the bench: started, done, or failed.", fields=(
    Field("step", "string", "`connect`, `launch`, `init_automation`, `version_overrides`, `run_workflow`..."),
    Field("status", OneOf(("running", "done", "error")), "Where it is."),
    Field("message", "string", "The same, for a person."),
))

#: `trace_workflow_steps` and `not_wired`: a step of the workflow the bench runs.
BENCH_WORKFLOW_STEP_EVENT = Event("workflow_step", doc="A step of the workflow under test.", fields=(
    Field("step", "string", "The step's id (an action of the run, or the workflow's type)."),
    Field("status", OneOf(("running", "done", "failed", "error")), "Where it is."),
    Field("error", "string", "What went wrong (`error`).", optional=True),
))

#: `setup_log_sink`: every log line of the run. Not the shared `log` line: it names its module,
#: its function and its time, and says `text`, not `message`.
BENCH_LOG_EVENT = Event("log", doc="A log line of the run, as loguru wrote it.", fields=(
    Field("level", "string", "debug, info, success, warning, error..."),
    Field("text", "string", "The line."),
    Field("module", "string", "The module that wrote it."),
    Field("function", "string", "The function that wrote it."),
    Field("ts", "string", "When, `HH:MM:SS.mmm`."),
))

#: `init_automation`: every `xpath()` call the selector tracer sees.
BENCH_SELECTOR_EVENT = Event("selector_event", doc="One selector looked up on the screen.", fields=(
    Field("xpath", "string", "The selector."),
    Field("found", "bool", "Something matched."),
    Field("elapsed_ms", "number", "How long the lookup took."),
    Field("step", "string", "The workflow step it belongs to (`__unknown__` outside one)."),
    Field("error", "string", "Why the lookup failed.", nullable=True),
    Field("screen", "string", "The screen the log says the run is on (`unknown`)."),
))

#: The bench's patched `IPCEmitter`, its lifecycle and the UI watchdog (`WorkflowWatchdog`).
BENCH_ACTION_EVENT = Event("action_event", doc="Something the run did or the bench saw.", fields=(
    Field("action", "string", "`follow`, `like`, `profile_visit`, `language_detected`, `watchdog_started`, "
                              "`stuck_detected`, `workflow_not_wired`..."),
    Field("username", "string", "The account it concerns, empty when none."),
    Field("success", "bool", "It went through."),
    Field("data", "json", "What it carries, per action."),
))

_STEP_SUMMARY = Shape(name="WorkflowTestStepSummary", doc="One step of the run, as the tracer saw it.", fields=(
    Field("name", "string", "The step."),
    Field("success", "bool", "It went through."),
    Field("error", "string", "Why not.", nullable=True),
    Field("duration_ms", "number", "How long it took."),
    Field("xpath_calls", "int", "Selectors looked up."),
    Field("xpath_found", "int", "Found."),
    Field("xpath_not_found", "int", "Not found."),
))

_XPATH_STAT = Shape(name="WorkflowTestXPathStat", doc="One selector over the run.", fields=(
    Field("xpath", "string", "The selector."),
    Field("total_calls", "int", "Lookups."),
    Field("found_count", "int", "Found."),
    Field("not_found_count", "int", "Not found."),
    Field("error_count", "int", "Failed."),
    Field("avg_ms", "number", "Mean lookup time."),
    Field("steps_used_in", ListOf("string"), "The steps that looked it up."),
    Field("screens_used_in", ListOf("string"), "The screens it was looked up on."),
))

_BENCH_RESULTS = (
    ("profiles_visited", "Profiles visited."),
    ("profiles_interacted", "Profiles interacted with."),
    ("likes", "Likes."),
    ("follows", "Follows."),
    ("comments", "Comments."),
    ("stories_watched", "Stories watched."),
    ("errors", "Errors."),
)

#: The bench's own `BaseStatsManager` callback. Not the automation's `instagram_stats`: it carries
#: the whole `get_summary()` (rates, duration, the error list), not the run's counters.
BENCH_STATS_EVENT = Event("instagram_stats", doc="The run's summary, after each counter change.", fields=(
    Field("stats", Shape(name="WorkflowTestLiveStats", doc="`BaseStatsManager.get_summary()`.", fields=(
        Field("workflow_type", "string", "The workflow."),
        Field("duration", "string", "Time spent, `HH:MM:SS`."),
        Field("duration_seconds", "number", "The same, in seconds."),
        *(Field(key, "int", doc) for key, doc in (
            ("profiles_visited", "Profiles visited."),
            ("profiles_interacted", "Profiles interacted with."),
            ("profiles_filtered", "Profiles refused by a filter."),
            ("skipped", "Profiles skipped."),
            ("private_profiles", "Private profiles met."),
            ("likes", "Likes."),
            ("follows", "Follows."),
            ("comments", "Comments."),
            ("stories_watched", "Stories watched."),
            ("story_likes", "Stories liked."),
            ("errors", "Errors."),
        )),
        Field("likes_per_hour", "number", "Likes per hour."),
        Field("follows_per_hour", "number", "Follows per hour."),
        Field("profiles_per_hour", "number", "Profiles per hour."),
        Field("error_list", ListOf("string"), "The errors, for a person."),
    )), "The summary."),
))

#: `build_workflow_report`: the tracer's report, plus what the run was asked and what it did.
BENCH_REPORT_EVENT = Event("test_report", doc="The bench's verdict, its last line.", fields=(
    Field("total_xpath_calls", "int", "Selector lookups."),
    Field("unique_xpaths", "int", "Distinct selectors."),
    Field("unique_xpaths_found", "int", "Distinct selectors found at least once."),
    Field("unique_xpaths_never_found", "int", "Never found."),
    Field("unique_xpaths_errored", "int", "Failed at least once."),
    Field("compatibility_score", "number", "Found over distinct, in percent."),
    Field("steps", ListOf(_STEP_SUMMARY), "The run's steps."),
    Field("xpath_stats", ListOf(_XPATH_STAT), "The run's selectors."),
    Field("never_found_xpaths", ListOf("string"), "Selectors never found."),
    Field("errored_xpaths", ListOf("string"), "Selectors that failed."),
    Field("workflow", Shape(name="WorkflowTestRunInfo", doc="What the bench ran.", fields=(
        Field("type", "string", "The workflow."),
        Field("target", "string", "Its target."),
        Field("success", "bool", "The run went through."),
        Field("error", "string", "Why not.", nullable=True),
        Field("elapsed_seconds", "number", "How long it ran."),
        Field("limits", MapOf("number"), "The limits it was given."),
        Field("probabilities", MapOf("number"), "The probabilities it was given."),
        Field("session_duration", "int", "Its session budget, in minutes."),
        Field("delays", MapOf("number"), "The pause range it was given, when one.", nullable=True),
    )), "The run."),
    Field("expected_results", Shape(name="WorkflowTestExpectedResults", doc="What the limits allow.", fields=tuple(
        Field(key, "int", doc) for key, doc in (
            ("profiles", "Profiles."), ("likes", "Likes."), ("follows", "Follows."),
            ("comments", "Comments."), ("stories", "Stories."),
        )
    )), "What the run should have done."),
    Field("actual_results", Shape(name="WorkflowTestActualResults", doc="The run's last counters.", fields=tuple(
        Field(key, "int", doc) for key, doc in _BENCH_RESULTS
    )), "What it did."),
    Field("functional", Shape(name="WorkflowTestFunctional", doc="Did the run do its job.", fields=(
        Field("success", "bool", "It did."),
        Field("notes", ListOf("string"), "Why not."),
    )), "The functional verdict."),
    Field("app", "string", "The app tested."),
    Field("version", "string", "Its version."),
    Field("device_id", "string", "The phone."),
))

WORKFLOW_TEST = ToolContract(
    name="WorkflowTest",
    bridge="workflow_test_bridge",
    doc="The Lab's workflow bench: a production run with its selectors traced.",
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        BENCH_LOG_EVENT,
        BENCH_STEP_EVENT,
        BENCH_WORKFLOW_STEP_EVENT,
        BENCH_SELECTOR_EVENT,
        BENCH_ACTION_EVENT,
        BENCH_STATS_EVENT,
        # The run's step telemetry, through the sink `init_automation` configures.
        STEP_METRIC_EVENT,
        BENCH_REPORT_EVENT,
    ),
)

# ------------------------------------------------------------------------------ selector bench

_XPATH_RESULT = Shape(name="SelectorTestXPathResult", doc="One selector of a field, on the screen.", fields=(
    Field("xpath", "string", "The selector."),
    Field("found", "bool", "It matched."),
    Field("error", "string", "Why the lookup failed.", nullable=True),
    Field("elapsed_ms", "number", "How long it took."),
    Field("mode", OneOf(("xml_snapshot", "live_device")), "On one dump of the screen, or live."),
))

_FIELD_RESULT = Shape(name="SelectorTestFieldResult", doc="One selector field of the catalogue.", fields=(
    Field("action", "string", "`domain.field`."),
    Field("domain", "string", "Its domain."),
    Field("field", "string", "Its field."),
    Field("source", "string", "Where the catalogue took it from."),
    Field("has_match", "bool", "One of its selectors matched."),
    Field("xpaths", ListOf(_XPATH_RESULT), "Its selectors."),
))

SELECTOR_TEST = ToolContract(
    name="SelectorTest",
    bridge="selector_test_bridge",
    doc="The selector bench: every selector of the installed version, on one screen.",
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        Event("progress", doc="Fields tested so far, every five.", fields=(
            Field("current", "int", "Tested."),
            Field("total", "int", "To test."),
            Field("action", "string", "The last one."),
        )),
        Event("test_results", doc="The bench's verdict.", fields=(
            Field("app", "string", "The app tested."),
            Field("version", "string", "The version installed."),
            Field("device_id", "string", "The phone."),
            Field("total_actions", "int", "Fields tested."),
            Field("total_xpaths", "int", "Selectors tested."),
            Field("passed", "int", "Fields with a match."),
            Field("failed", "int", "Fields without one."),
            Field("domain_summary", MapOf(Shape(name="SelectorTestDomainSummary", doc="One domain.", fields=(
                Field("total", "int", "Fields."),
                Field("passed", "int", "With a match."),
                Field("failed", "int", "Without one."),
            ))), "Per domain."),
            Field("results", ListOf(_FIELD_RESULT), "Per field."),
            Field("baseline_version", "string", "The version the catalogue describes."),
            Field("overrides_applied", "int", "Selectors the version's overrides patched."),
            Field("language", "string", "The language detected on the screen (`unknown`)."),
            Field("skipped_not_xpath", "int", "Entries that are not selectors (labels, ids), not tested."),
            Field("skipped_empty", "int", "Fields the language filter emptied."),
        )),
    ),
)

# ------------------------------------------------------------------------------ Lab action session

_SESSION_ERROR_EVENT = Event("error", doc="A command or the session failed.", fields=(
    Field("success", "bool", "Always false."),
    Field("message", "string", "What went wrong, for a person."),
    Field("request_id", "string", "The command it answers.", nullable=True, optional=True),
    Field("error", "string", "The exception.", optional=True),
    Field("traceback", "string", "Diagnostic context.", optional=True),
))

ACTION_SESSION = ToolContract(
    name="ActionSession",
    bridge="action_session_bridge",
    doc="The Cartography Lab's action session: one connection, one action per command.",
    events=(
        LOG_EVENT,
        STEP_METRIC_EVENT,
        Event("session_ready", doc="The phone is connected and the actions are loaded.", fields=(
            Field("success", "bool", "Always true."),
            Field("device_id", "string", "The phone."),
            Field("platform", OneOf(("instagram", "tiktok")), "The platform of the actions."),
            Field("language_optimization", "json", "The language detected and the selectors it kept."),
        )),
        Event("result", doc="One action run, its traces and its artifacts.", fields=(
            Field("request_id", "string", "The command it answers.", nullable=True),
            Field("success", "bool", "The action went through."),
            Field("message", "string", "What happened, for a person."),
            Field("selector_traces", "json", "Every selector the action looked up."),
            Field("ui_action_trace", "json", "What the action did on the screen.", nullable=True),
            Field("artifacts", "json", "Screenshots, dumps and reports, as files.", nullable=True),
            Field("language_optimization", "json", "The language and its selectors, for this action."),
            Field("transition", "json", "The screen before and after.", nullable=True),
            Field("phase_timings", "json", "How long each phase took.", optional=True),
            Field("perf_fast", "bool", "Artifacts skipped for speed.", optional=True),
            Field("details", "json", "What the action read (handles, counts...).", nullable=True, optional=True),
        )),
        _SESSION_ERROR_EVENT,
    ),
)

# ------------------------------------------------------------------------------ debug tooling

INSTAGRAM_DEBUG = ToolContract(
    name="InstagramDebug",
    bridge="desktop_bridge",
    mode="debugMode",
    doc="The debug tooling of the Instagram bridge: a capture of the screen, or its problem pages.",
    events=(
        ERROR_EVENT,
        LOG_EVENT,
        Event("debug_result", doc="What the command found.", fields=(
            Field("success", "bool", "The command ran."),
            Field("screenshotPath", "string", "The screenshot (`analyze`).", nullable=True, optional=True),
            Field("dumpPath", "string", "The screen's tree (`analyze`).", nullable=True, optional=True),
            Field("detected", "bool", "A problem page was on screen (`detect`).", optional=True),
            Field("handled", "bool", "It was closed (`detect`).", optional=True),
        )),
    ),
)

TOOLS = (WORKFLOW_TEST, SELECTOR_TEST, ACTION_SESSION, INSTAGRAM_DEBUG)

__all__ = ["ACTION_SESSION", "INSTAGRAM_DEBUG", "SELECTOR_TEST", "TOOLS", "WORKFLOW_TEST"]
