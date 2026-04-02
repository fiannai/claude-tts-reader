#!/usr/bin/env python3
"""
Read Claude's assistant responses aloud via Kokoro TTS.

Primary: uses last_assistant_message from hook input (always available on Stop).
Fallback: position-tracked transcript reading for mid-turn text blocks.

On first encounter with a transcript, seeds position and still reads the
last_assistant_message so the first response in a session is never silent.
"""
import hashlib
import json
import os
import subprocess
import sys

DEBUG_LOG = os.path.expanduser("~/tts_hook_debug.log")
DISABLED_FLAG = os.path.expanduser("~/.tts_disabled")
PID_FILE = os.path.expanduser("~/.tts_speak_pid")
POSITION_DIR = os.path.expanduser("~/.tts_positions")


def log(msg):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{msg}\n")


def speak(text):
    """Send text to speak.py for TTS playback."""
    speak_script = os.path.join(os.path.dirname(__file__), "..", "tools", "speak.py")
    try:
        proc = subprocess.Popen(
            [sys.executable, speak_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))

        stdout, stderr = proc.communicate(input=text)
        log(f"speak.py exit code: {proc.returncode}")
        if stderr:
            log(f"speak.py stderr: {stderr}")

        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception as e:
        log(f"Error running speak.py: {e}")


log("=== Hook triggered ===")

if os.path.exists(DISABLED_FLAG):
    log("Reader is disabled, skipping")
    sys.exit(0)

try:
    hook_input = json.load(sys.stdin)
except Exception as e:
    log(f"Error reading stdin: {e}")
    sys.exit(1)

# Kill any existing TTS playback before starting new one
if os.path.exists(PID_FILE):
    try:
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(old_pid)],
            capture_output=True, check=False,
        )
        log(f"Killed previous TTS process {old_pid}")
    except (ValueError, IOError):
        pass
subprocess.run(
    ["taskkill", "/F", "/IM", "ffplay.exe"],
    capture_output=True, check=False,
)

# Get transcript path for position tracking
transcript_path = hook_input.get("transcript_path")

# Get last_assistant_message directly from hook input (most reliable)
last_msg = hook_input.get("last_assistant_message", "").strip()

# Position tracking setup
has_transcript = transcript_path and os.path.exists(transcript_path)
first_encounter = False
texts_from_transcript = []

if has_transcript:
    os.makedirs(POSITION_DIR, exist_ok=True)
    transcript_hash = hashlib.md5(transcript_path.encode()).hexdigest()[:12]
    position_file = os.path.join(POSITION_DIR, f"{transcript_hash}.pos")

    # Count total lines
    total_lines = 0
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for _ in f:
            total_lines += 1

    first_encounter = not os.path.exists(position_file)

    if first_encounter:
        # Seed position but DON'T exit — we still have last_msg to read
        log(f"First encounter with transcript, seeding position to {total_lines}")
        with open(position_file, 'w') as f:
            f.write(str(total_lines))
    else:
        # Read saved position
        last_read = 0
        try:
            with open(position_file, 'r') as f:
                content = f.read().strip()
                if content:
                    last_read = int(content)
        except (ValueError, IOError):
            last_read = 0

        if last_read < total_lines:
            # Read new assistant text since last position
            current_line = 0
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        current_line += 1
                        if current_line <= last_read:
                            continue
                        try:
                            entry = json.loads(line.strip())
                            if entry.get("type") != "assistant":
                                continue
                            message = entry.get("message", {})
                            if message.get("role") != "assistant":
                                continue
                            content = message.get("content", [])
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text = item.get("text", "").strip()
                                    if text:
                                        texts_from_transcript.append(text)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                log(f"Error reading transcript: {e}")

            # Save new position
            try:
                with open(position_file, 'w') as f:
                    f.write(str(current_line))
            except IOError as e:
                log(f"Error saving position: {e}")

            log(f"Read lines {last_read + 1}-{current_line}, found {len(texts_from_transcript)} text blocks from transcript")
        else:
            log("No new lines in transcript")

# Decide what to read:
# - If transcript gave us multiple text blocks, use those (catches mid-turn text)
# - If transcript gave us nothing but we have last_msg, use that (reliable fallback)
# - If transcript gave us one block, compare with last_msg to avoid duplicate

if texts_from_transcript:
    full_text = "\n\n".join(texts_from_transcript)
    log(f"Using {len(texts_from_transcript)} text blocks from transcript")
elif last_msg:
    full_text = last_msg
    log(f"Using last_assistant_message from hook input")
else:
    log("No text to speak")
    sys.exit(0)

log(f"Text length: {len(full_text)} chars")
log(f"Preview: {full_text[:200]}...")

speak(full_text)

log("=== Hook finished ===")
sys.exit(0)
