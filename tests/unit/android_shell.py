"""The part of an Android phone's shell that the bot's keyboard commands use, for fake phones.

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
