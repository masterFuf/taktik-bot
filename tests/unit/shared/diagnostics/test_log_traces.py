"""A trace asked with `exc_info=True` is written, whatever loguru logger a module of the engine holds.

The engine's modules log through loguru. The standard library's way to ask for the trace of the
exception being handled, `logger.error(message, exc_info=True)`, is not loguru's: loguru filed the
keyword among the record's extra fields and wrote the message alone. The crash path of the Instagram
session loop (`InstagramAutomation.run_workflow`) asked for its trace that way and left none in the log.

These tests go through the package's own logging setup (importing `taktik` installs it), never through
a setup of their own: what they prove is what every host gets (bridges, CLI, Lab, tests).
"""

import io

import pytest
from loguru import logger

import taktik  # noqa: F401  (the package's logging setup, the subject of these tests)


class DeviceGone(RuntimeError):
    """The exception the tests log."""


def _lose_the_device():
    raise DeviceGone('device gone')


@pytest.fixture
def written():
    """What a sink of the run's log receives."""
    out = io.StringIO()
    sink = logger.add(out, format='{level} | {message}', level='DEBUG')
    yield out
    logger.remove(sink)


def test_exc_info_writes_the_trace_of_the_exception_being_handled(written):
    try:
        _lose_the_device()
    except DeviceGone:
        logger.error('Critical error executing workflow: device gone', exc_info=True)

    text = written.getvalue()
    assert 'Traceback' in text, text
    assert '_lose_the_device' in text, "the trace does not reach the frame that raised"
    assert 'DeviceGone: device gone' in text


def test_a_bound_logger_writes_it_too(written):
    """What a module holds, as the session loop does: `logger.bind(module=...)`."""
    bound = logger.bind(module='instagram-automation')
    try:
        _lose_the_device()
    except DeviceGone:
        bound.error('Critical error executing workflow: device gone', exc_info=True)

    assert 'DeviceGone: device gone' in written.getvalue()


def test_an_exception_given_as_exc_info_writes_its_own_trace(written):
    """The standard library also takes the exception itself, outside its `except`."""
    try:
        _lose_the_device()
    except DeviceGone as error:
        caught = error

    logger.warning('The device was lost earlier', exc_info=caught)

    text = written.getvalue()
    assert '_lose_the_device' in text, text
    assert 'DeviceGone: device gone' in text


def test_a_type_value_traceback_triple_writes_its_trace(written):
    """The third form the standard library takes, what `sys.exc_info()` returns."""
    try:
        _lose_the_device()
    except DeviceGone as error:
        caught = (type(error), error, error.__traceback__)

    logger.warning('The device was lost earlier', exc_info=caught)

    text = written.getvalue()
    assert '_lose_the_device' in text, text
    assert 'DeviceGone: device gone' in text


def test_without_exc_info_the_message_stays_alone(written):
    try:
        _lose_the_device()
    except DeviceGone:
        logger.error('Step failed', exc_info=False)
        logger.error('Step failed again')

    assert 'Traceback' not in written.getvalue()
