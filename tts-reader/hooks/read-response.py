#!/usr/bin/env python3
"""
Read Claude's assistant responses aloud via the TTS service.

Text sources:
  Primary: new assistant text blocks in the transcript since the saved
  line cursor (catches mid-turn text blocks).
  Fallback: last_assistant_message from hook input (always available on
  Stop, survives the transcript-flush race).

Dedup is content-based: a hash of every spoken block is remembered per
transcript, and any block whose hash was already spoken is skipped. The
line cursor is only a scan optimization — correctness comes from the
hashes, so the transcript-flush race can no longer cause double-reads
or skips.

This script ALWAYS exits 0. A non-zero exit means the interpreter
itself is missing (hooks.json uses that to fall back between python3
and python — a failing script must not retrigger the fallback and speak
twice). Every failure, including unexpected crashes, is written to the
debug log via the top-level handler: the hook must never fail silently.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import traceback

IS_WINDOWS = os.name == "nt"

DEBUG_LOG = os.path.expanduser("~/tts_hook_debug.log")
DISABLED_FLAG = os.path.expanduser("~/.tts_disabled")
MANUAL_FLAG = os.path.expanduser("~/.tts_manual")
LAST_MSG_FILE = os.path.expanduser("~/.tts_last_message")
PID_FILE = os.path.expanduser("~/.tts_speak_pid")
STATE_DIR = os.path.expanduser("~/.tts_positions")

MAX_REMEMBERED_HASHES = 50


def log(msg):
    """Append to the debug log. Never raises — logging must not kill the hook."""
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def text_hash(text):
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def kill_previous_playback():
    """Stop any TTS still playing from a previous turn (cross-platform)."""
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
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(old_pid)],
                    capture_output=True, check=False,
                )
            else:
                # speak.py is spawned with start_new_session=True, so its
                # process group includes ffplay — kill the whole group.
                os.killpg(old_pid, signal.SIGTERM)
            log(f"Killed previous TTS process {old_pid}")
        except (OSError, subprocess.SubprocessError) as e:
            log(f"Previous TTS process {old_pid} not killable: {e}")

    # Best-effort sweep for orphaned players (parity with old behavior).
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"],
                           capture_output=True, check=False)
        else:
            subprocess.run(["pkill", "-x", "ffplay"],
                           capture_output=True, check=False)
    except Exception as e:
        log(f"Orphan player sweep failed: {e}")


def speak(text):
    """Send text to speak.py for TTS playback."""
    speak_script = os.path.join(os.path.dirname(__file__), "..", "tools", "speak.py")
    kwargs = {}
    if not IS_WINDOWS:
        # New session = new process group, so the next hook can killpg us.
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [sys.executable, speak_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))

    _, stderr = proc.communicate(input=text)
    log(f"speak.py exit code: {proc.returncode}")
    if stderr:
        log(f"speak.py stderr: {stderr.strip()}")

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def state_paths(transcript_path):
    os.makedirs(STATE_DIR, exist_ok=True)
    key = hashlib.md5(transcript_path.encode()).hexdigest()[:12]
    return (os.path.join(STATE_DIR, f"{key}.pos"),
            os.path.join(STATE_DIR, f"{key}.hashes"))


def load_spoken_hashes(hash_file):
    try:
        with open(hash_file, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (IOError, json.JSONDecodeError, ValueError):
        pass
    return []


def save_spoken_hashes(hash_file, hashes):
    try:
        with open(hash_file, "w") as f:
            json.dump(hashes[-MAX_REMEMBERED_HASHES:], f)
    except IOError as e:
        log(f"Error saving hashes: {e}")


def read_new_transcript_texts(transcript_path, pos_file):
    """Return (texts, first_encounter). Advances the line cursor."""
    total_lines = 0
    with open(transcript_path, "r", encoding="utf-8") as f:
        for _ in f:
            total_lines += 1

    first_encounter = not os.path.exists(pos_file)
    last_read = 0
    if not first_encounter:
        try:
            with open(pos_file, "r") as f:
                content = f.read().strip()
                if content:
                    last_read = int(content)
        except (ValueError, IOError):
            last_read = 0

    texts = []
    if not first_encounter and last_read < total_lines:
        current_line = 0
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                current_line += 1
                if current_line <= last_read:
                    continue
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                message = entry.get("message", {})
                if message.get("role") != "assistant":
                    continue
                for item in message.get("content", []):
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "").strip()
                        if text:
                            texts.append(text)
        log(f"Scanned lines {last_read + 1}-{current_line}, "
            f"{len(texts)} text blocks")

    try:
        with open(pos_file, "w") as f:
            f.write(str(total_lines))
    except IOError as e:
        log(f"Error saving position: {e}")

    if first_encounter:
        log(f"First encounter with transcript, cursor seeded to {total_lines}")

    return texts, first_encounter


def main():
    log("=== Hook triggered ===")

    if os.path.exists(DISABLED_FLAG):
        log("Reader is disabled, skipping")
        return

    try:
        hook_input = json.load(sys.stdin)
    except Exception as e:
        log(f"Error reading stdin: {e}")
        return

    transcript_path = hook_input.get("transcript_path")
    last_msg = (hook_input.get("last_assistant_message") or "").strip()

    candidates = []
    spoken = []
    hash_file = None

    if transcript_path and os.path.exists(transcript_path):
        pos_file, hash_file = state_paths(transcript_path)
        spoken = load_spoken_hashes(hash_file)
        try:
            candidates, _ = read_new_transcript_texts(transcript_path, pos_file)
        except Exception as e:
            log(f"Error reading transcript: {e}")

    # Fallback / union: last_msg covers the transcript-flush race (the
    # turn's lines may not be on disk yet when Stop fires).
    if last_msg and text_hash(last_msg) not in {text_hash(t) for t in candidates}:
        candidates.append(last_msg)

    # Save ONLY the turn's final message for read-last.py replay —
    # mid-turn status blocks are noise when someone asks to hear "the
    # last response". Saved before dedup: it's replayable even if it
    # was already spoken.
    last_final = last_msg or (candidates[-1] if candidates else "")
    if last_final:
        try:
            with open(LAST_MSG_FILE, "w", encoding="utf-8") as f:
                f.write(last_final)
        except IOError as e:
            log(f"Error saving last message: {e}")

    # Content dedup: never speak a block twice, regardless of which
    # source it arrived from or when the transcript got flushed.
    to_speak = []
    for t in candidates:
        h = text_hash(t)
        if h in spoken:
            log(f"Skipping already-spoken block {h}")
            continue
        to_speak.append(t)
        spoken.append(h)

    if not to_speak:
        log("No new text to speak")
        return

    if hash_file:
        # Record before speaking: a concurrent/next hook must never
        # re-speak these blocks even if this playback gets killed.
        save_spoken_hashes(hash_file, spoken)

    full_text = "\n\n".join(to_speak)

    if os.path.exists(MANUAL_FLAG):
        log(f"Manual mode: not speaking ({len(to_speak)} new block(s); final message saved for replay)")
        return

    kill_previous_playback()
    log(f"Speaking {len(to_speak)} block(s), {len(full_text)} chars")
    log(f"Preview: {full_text[:200]}...")

    speak(full_text)

    log("=== Hook finished ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never silent, never non-zero (non-zero would retrigger the
        # interpreter fallback in hooks.json and double-speak).
        log("UNEXPECTED CRASH:\n" + traceback.format_exc())
    sys.exit(0)
