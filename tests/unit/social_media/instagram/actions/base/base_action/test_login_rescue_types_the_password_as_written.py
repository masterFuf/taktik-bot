"""The login's pasted rescue (`TypingMixin._adb_input_text`): the phone types the text as written.

It wrote `input text "<text>"` with only `'` and `"` escaped: inside double quotes the phone's
shell still expands `$` and backquotes and keeps a backslash before `'`. A password `Pa$$word`
was typed `Pa<pid of the shell>word`, and the rescue said True. What the phone reads is replayed
by `unit.android_shell.phone_words` on the line the shared door sends.
"""

import types

import pytest

from taktik.core.shared.device.adb import device_command_line
from taktik.core.social_media.instagram.actions.base.base_action.typing import TypingMixin
from unit.android_shell import phone_words


def _typed_by_the_phone(text):
    sent = []
    mixin = types.SimpleNamespace(
        _get_device_serial=lambda: "SERIAL",
        _run_adb_shell=lambda serial, command: sent.append(device_command_line(command)) or "",
        logger=types.SimpleNamespace(debug=lambda *a: None, error=lambda *a: None),
    )
    assert TypingMixin._adb_input_text(mixin, text) is True
    (line,) = sent
    return phone_words(line)


@pytest.mark.parametrize("password", ["Pa$$word", "it's", 'say"hi', "back\\slash", "`id`", "a&b|c;d"])
def test_the_password_reaches_input_text_as_written(password):
    assert _typed_by_the_phone(password) == ["input", "text", password]


def test_spaces_still_go_as_the_input_command_reads_them():
    assert _typed_by_the_phone("two words") == ["input", "text", "two%swords"]
