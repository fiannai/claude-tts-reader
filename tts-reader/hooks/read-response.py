#!/usr/bin/env python3
"""
Read Claude's last assistant response aloud via Kokoro TTS.
Simple: find the last assistant text block in the transcript, read it.
No position tracking, no state files.
"""
import json
import os
import subprocess
import sys

DEBUG_LOG = os.path.expanduser("~/tts_hook_debug.log")
DISABLED_FLAG = os.path.expanduser("~/.tts_disabled")
PID_FILE = os.path.expanduser("~/.tts_speak_pid")


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

# Find the last assistant message in the transcript
last_texts = []
try:
    with open(transcript_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
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
                        last_texts.append(text)
            if last_texts:
                break
        except json.JSONDecodeError:
            continue
except Exception as e:
    log(f"Error reading transcript: {e}")
    sys.exit(1)

if not last_texts:
    log("No assistant text found")
    sys.exit(0)

full_text = " ".join(last_texts)
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
