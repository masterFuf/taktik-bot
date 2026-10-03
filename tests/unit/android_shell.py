"""The part of an Android phone's shell that the bot's adb commands meet, for fake phones.

Two parts: how the phone's shell reads an adb line (`adb_line`, `phone_words`, at the end), and
the keyboard check below.

The bot broadcasts to the Taktik Keyboard only if the phone is on it at that moment, in ONE adb
command that the phone's shell runs (`taktik_keyboard._broadcast_to_taktik_keyboard`):

    ime=$(settings get secure default_input_method); if [ "$ime" = "<id>" ]; then <command>; else echo "<text> $ime"; fi

A fake phone that models its input method hands such a command to `run_keyboard_check`, with
the input method it is on and its own way of running `<command>`: the shell runs `<command>` when
the phone is on `<id>`, otherwise answers the echo. Checked on a Pixel 4a (Android 13) on
2026-09-28: the shell answered the echo, with Gboard's id, while on Gboard.

Imported as `unit.android_shell` (the `tests` folder is on the path of every pytest run, as the
package of `tests/unit/conftest.py`).
"""

READ_KEYBOARD = "settings get secure default_input_method"
_CHECK_PREFIX = f"ime=$({READ_KEYBOARD});"


def is_keyboard_check(command: str) -> bool:
    return command.startswith(_CHECK_PREFIX)


def run_keyboard_check(command: str, current_ime: str, run):
    """What the phone's shell answers to a keyboard check, the phone being on `current_ime`.
    `run(inner_command)` runs the command the check guards."""
    wanted = command.split('[ "$ime" = "', 1)[1].split('" ]', 1)[0]
    guarded = command.split("; then ", 1)[1].split("; else ", 1)[0]
    echoed = command.split('; else echo "', 1)[1].split('"; fi', 1)[0]
    if current_ime == wanted:
        return run(guarded)
    return echoed.replace("$ime", current_ime)


# --- what the phone's shell reads of an adb line ----------------------------------------------
#
# `adb shell a b c` joins its arguments with spaces and sends ONE line; the phone's shell splits it
# again. `adb_line(argv)` is that line, `phone_words(line)` the words the phone's shell hands to the
# command, by the POSIX rules of its `sh` (mksh/toybox on Android). A line the shell would REWRITE
# (expand a `$` or a backquote, run a `|`, `&`, `;`, `<`, `>`, glob a `*`) raises
# `ShellWouldRewrite`: what the caller wrote is then not what the phone runs.

_OPERATORS = set("|&;<>()")
_GLOB = set("*?[")
_BLANKS = " \t\n"


class ShellWouldRewrite(ValueError):
    """The phone's shell would not read this line as plain words."""


def adb_line(argv) -> str:
    """The line adb sends to the phone for the arguments it was launched with."""
    argv = list(argv)
    return " ".join(argv[argv.index("shell") + 1:])


def phone_words(line: str) -> list:
    words, current, in_word, i = [], [], False, 0
    while i < len(line):
        char = line[i]
        if char in _BLANKS:
            if in_word:
                words.append("".join(current))
                current, in_word = [], False
            i += 1
        elif char == "'":
            end = line.find("'", i + 1)
            if end < 0:
                raise ShellWouldRewrite(f"unterminated ' in {line!r}")
            current.append(line[i + 1:end])
            in_word, i = True, end + 1
        elif char == '"':
            in_word, i = True, i + 1
            while True:
                if i >= len(line):
                    raise ShellWouldRewrite(f'unterminated " in {line!r}')
                inner = line[i]
                if inner == '"':
                    i += 1
                    break
                if inner in "$`":
                    raise ShellWouldRewrite(f"the shell expands {inner} inside double quotes: {line!r}")
                if inner == "\\" and i + 1 < len(line) and line[i + 1] in '$`"\\n':
                    current.append(line[i + 1])
                    i += 2
                    continue
                current.append(inner)
                i += 1
        elif char == "\\":
            if i + 1 >= len(line):
                raise ShellWouldRewrite(f"a lone backslash ends {line!r}")
            current.append(line[i + 1])
            in_word, i = True, i + 2
        elif char in "$`":
            raise ShellWouldRewrite(f"the shell expands {char}: {line!r}")
        elif char in _OPERATORS:
            raise ShellWouldRewrite(f"the shell runs the operator {char}: {line!r}")
        elif char in _GLOB:
            raise ShellWouldRewrite(f"the shell globs {char}: {line!r}")
        elif not in_word and char in "#~":
            raise ShellWouldRewrite(f"the shell reads {char} at the start of a word: {line!r}")
        else:
            current.append(char)
            in_word, i = True, i + 1
    if in_word:
        words.append("".join(current))
    return words
