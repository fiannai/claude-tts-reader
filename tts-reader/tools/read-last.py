#!/usr/bin/env python3
"""
Speak the last saved assistant message on demand.

The Stop hook saves every turn's would-be-spoken text to
~/.tts_last_message (in every mode). This tool replays it: the caller
passes no text at all, so triggering a read costs nothing regardless of
message length. Primary use is manual mode (~/.tts_manual), where the
hook stays silent until asked; it also works in auto mode as a
"read that again".

Fire-and-forget: playback is handed to speak.py in its own process
group and this tool exits immediately, so a caller's timeout can't cut
audio short. Running it again (or a new auto-read) supersedes the
current playback.
"""
import os
import signal
import subprocess
import sys

IS_WINDOWS = os.name == "nt"
LAST_MSG_FILE = os.path.expanduser("~/.tts_last_message")
PID_FILE = os.path.expanduser("~/.tts_speak_pid")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def kill_previous_playback():
    old_pid = None
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
        except (ValueError, IOError):
            old_pid = None
    if old_pid:
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(old_pid)],
                               capture_output=True, check=False)
            else:
                os.killpg(old_pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"],
                           capture_output=True, check=False)
        else:
            subprocess.run(["pkill", "-x", "ffplay"],
                           capture_output=True, check=False)
    except Exception:
        pass


def main() -> int:
    try:
        with open(LAST_MSG_FILE, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except IOError:
        print("No saved message to read yet.", file=sys.stderr)
        return 1
    if not text:
        print("Saved message is empty.", file=sys.stderr)
        return 1

    kill_previous_playback()

    kwargs = {}
    if not IS_WINDOWS:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [sys.executable, os.path.join(SCRIPT_DIR, "speak.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        **kwargs,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))
    proc.stdin.write(text)
    proc.stdin.close()
    print(f"Reading {len(text)} chars.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
