#!/usr/bin/env python3
"""
Read Claude's assistant responses aloud via Kokoro TTS.
Tracks position per transcript file. On first encounter of a transcript,
seeds position to end-of-file so it doesn't read history.
Kills any previous TTS before starting.
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


log("=== Hook triggered ===")

if os.path.exists(DISABLED_FLAG):
    log("Reader is disabled, skipping")
    sys.exit(0)

try:
    hook_input = json.load(sys.stdin)
except Exception as e:
    log(f"Error reading stdin: {e}")
    sys.exit(1)

transcript_path = hook_input.get("transcript_path")
if not transcript_path or not os.path.exists(transcript_path):
    log("No transcript available")
    sys.exit(0)

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

# Per-transcript position tracking
os.makedirs(POSITION_DIR, exist_ok=True)
transcript_hash = hashlib.md5(transcript_path.encode()).hexdigest()[:12]
position_file = os.path.join(POSITION_DIR, f"{transcript_hash}.pos")

# Count total lines in transcript
total_lines = 0
with open(transcript_path, 'r', encoding='utf-8') as f:
    for _ in f:
        total_lines += 1

# First time seeing this transcript? Seed to current end so we don't read history.
first_encounter = not os.path.exists(position_file)
if first_encounter:
    log(f"First encounter with transcript, seeding position to {total_lines}")
    with open(position_file, 'w') as f:
        f.write(str(total_lines))
    sys.exit(0)

# Read saved position
last_read = 0
try:
    with open(position_file, 'r') as f:
        content = f.read().strip()
        if content:
            last_read = int(content)
except (ValueError, IOError):
    last_read = 0

# Nothing new
if last_read >= total_lines:
    log("No new lines in transcript")
    sys.exit(0)

# Read new assistant text since last position
texts = []
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
                            texts.append(text)
            except json.JSONDecodeError:
                continue
except Exception as e:
    log(f"Error reading transcript: {e}")
    sys.exit(1)

# Save new position
try:
    with open(position_file, 'w') as f:
        f.write(str(current_line))
except IOError as e:
    log(f"Error saving position: {e}")

log(f"Read lines {last_read + 1}-{current_line}, found {len(texts)} text blocks")

if not texts:
    log("No new assistant text to speak")
    sys.exit(0)

full_text = "\n\n".join(texts)
log(f"Text length: {len(full_text)} chars")
log(f"Preview: {full_text[:200]}...")

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

    stdout, stderr = proc.communicate(input=full_text)
    log(f"speak.py exit code: {proc.returncode}")
    if stderr:
        log(f"speak.py stderr: {stderr}")

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
except Exception as e:
    log(f"Error running speak.py: {e}")

log("=== Hook finished ===")
sys.exit(0)
