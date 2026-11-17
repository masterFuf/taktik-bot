"""A trace asked the standard library's way is written by loguru too.

The engine's modules log through loguru (`from loguru import logger`, sometimes `logger.bind(...)`); a
handful through the standard `logging`. The standard way to ask for the trace of the exception being
handled is `logger.error(message, exc_info=True)`. Loguru does not know that keyword: it filed it among
the record's extra fields and wrote the message alone, so a crash logged that way left no trace
(loguru 0.7.3). Loguru's own ways, `logger.exception(message)` and
`logger.opt(exception=True).error(message)`, are not changed.

`honour_exc_info` is a loguru patcher: loguru calls it on every record, before any sink writes it.
`install_exc_info_traces` sets it once on loguru's core, which every logger of the process shares,
bound ones included. The package's logging setup calls it (`taktik/__init__.py`), so every host gets
it: bridges, CLI, Lab, tests. In Symfony terms: one Monolog processor declared once for every channel,
instead of a fix at each call.
"""

import sys
from typing import TYPE_CHECKING

from loguru import logger

# The class of `record["exception"]`: loguru's stub declares it at the package root, for the type
# checker, but at run time it lives in a private module. requirements.lock pins loguru, and
# tests/unit/shared/diagnostics/test_log_traces.py fails if an upgrade moves it.
if TYPE_CHECKING:
    from loguru import Record, RecordException
else:
    from loguru._recattrs import RecordException


def honour_exc_info(record: "Record") -> None:
    """Give the record the exception its `exc_info` keyword asks for, as the standard library reads it.

    `exc_info=True`: the exception being handled; an exception: that one; a `(type, value, traceback)`
    tuple: as given. The keyword is taken out of the record's extra fields: it is not data of the run.
    An exception loguru already holds (`logger.exception`, `opt(exception=...)`) stays.
    """
    asked = record["extra"].pop("exc_info", None)
    if not asked or record["exception"] is not None:
        return
    if isinstance(asked, BaseException):
        error_type, error, traceback = type(asked), asked, asked.__traceback__
    elif isinstance(asked, tuple):
        error_type, error, traceback = asked
    else:
        error_type, error, traceback = sys.exc_info()
    if error_type is not None:
        record["exception"] = RecordException(error_type, error, traceback)


def install_exc_info_traces() -> None:
    """Set `honour_exc_info` on loguru's core, for every logger of the process."""
    logger.configure(patcher=honour_exc_info)


__all__ = ["honour_exc_info", "install_exc_info_traces"]
