"""Persistent Cartography Lab action session bridge."""

from bridges.common.runtime.entrypoint import CONFIG_ERROR, MISSING_CONFIG, run_bridge_main
from bridges.compat.diagnostics.runtime.action_test.session import (
    ActionSessionRun,
    report_action_session_entry_error,
)
from bridges.compat.diagnostics.runtime.events import configure_logger, configure_stdout


configure_stdout()
configure_logger()


def main():
    run_bridge_main(ActionSessionRun, usage="action_session_bridge <config.json>",
                    report_error=report_action_session_entry_error,
                    messages={MISSING_CONFIG: "No config file provided", CONFIG_ERROR: "Failed to read config: {error}"}, catch_crashes=False)


if __name__ == "__main__":
    main()
