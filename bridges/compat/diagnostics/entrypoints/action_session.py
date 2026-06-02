"""Persistent Cartography Lab action session bridge."""

from bridges.compat.diagnostics.runtime.action_test.session import run_action_session_bridge
from bridges.compat.diagnostics.runtime.events import configure_logger, configure_stdout


configure_stdout()
configure_logger()


def main():
    run_action_session_bridge()


if __name__ == "__main__":
    main()
