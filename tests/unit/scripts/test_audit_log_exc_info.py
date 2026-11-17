"""The exc_info audit finds a loguru logger given `exc_info=`, and only that."""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_log_exc_info as audit  # noqa: E402


def _calls(source: str) -> list:
    return [finding.call for finding in audit.scan_source(source)]


@pytest.mark.parametrize("source, expected", [
    ("from loguru import logger\nlogger.error('x', exc_info=True)", ["logger.error"]),
    ("from loguru import logger\nlog = logger.bind(module='m')\nlog.warning(f'{e}', exc_info=e)",
     ["log.warning"]),
    ("class A:\n    def f(self):\n        self.logger.debug('x', exc_info=True)", ["self.logger.debug"]),
    # A loguru logger re-exported by another module of the engine.
    ("from bridges.common.bridge_base import logger\nlogger.error('x', exc_info=True)", ["logger.error"]),
    ("from loguru import logger\nlogger.bind(a=1).error('x', exc_info=True)", ["logger.bind().error"]),
])
def test_exc_info_given_to_a_loguru_logger_is_found(source, expected):
    assert _calls(source) == expected


@pytest.mark.parametrize("source", [
    # The standard library's own way, on its own loggers.
    "import logging\nlogger = logging.getLogger(__name__)\nlogger.error('x', exc_info=True)",
    "import logging\nlogging.error('x', exc_info=True)",
    "import logging\nlogging.getLogger('taktik').warning('x', exc_info=True)",
    "import logging\nclass A:\n    def __init__(self):\n        self.log = logging.getLogger('a')\n"
    "    def f(self):\n        self.log.error('x', exc_info=True)",
    # The one way to write a trace with loguru.
    "from loguru import logger\nlogger.exception('x')",
    "from loguru import logger\nlogger.opt(exception=True).debug('x')",
    # A plain message, and loguru's own formatting on a written template.
    "from loguru import logger\nlogger.error(f'{x}')\nlogger.debug('a {} b', x)",
])
def test_what_is_not_exc_info_on_loguru_is_left_alone(source):
    assert _calls(source) == []


def test_the_engine_passes_exc_info_to_no_loguru_logger():
    assert [finding.render() for finding in audit.collect()] == []
