---
name: tts-setup
description: First-time setup for Claude TTS Reader — configure server, voice, and hotkey
user-invocable: true
disable-model-invocation: true
---

Run first-time setup for Claude TTS Reader.

## 1. Check prerequisites

Run these checks and report results:
- Python 3 is available
- `ffplay` is available (part of FFmpeg)
- Python `requests` library is installed

If `requests` is missing, offer to install it with `pip install requests`.
If `ffplay` is missing, tell the user to install FFmpeg.

## 2. Configure TTS server

Ask the user for their Kokoro TTS server URL (default: `http://localhost:8190`).
Test the connection: `curl -s <url>/api/status`
If it fails, warn but continue.

## 3. Choose a voice

Show available voices and ask the user to pick one:
- Female: af_heart, af_bella, af_nicole, af_sarah, af_sky
- Male: am_adam, am_michael, am_echo, am_onyx

Default is af_heart.

## 4. Write config

Write the config to `${CLAUDE_PLUGIN_ROOT}/tools/tts-config.json`:
```json
{
  "api_url": "<user's url>",
  "default_voice": "<user's choice>",
  "max_queue_size": 20,
  "request_timeout": 30,
  "sentence_pause_min_ms": 80,
  "sentence_pause_max_ms": 120,
  "batch_start_percent": 25
}
```

Also write the voice to `~/.tts_voice`.

## 5. Register Ctrl+Alt+S hotkey (Windows only)

On Windows, run this PowerShell to create a global hotkey:
```powershell
$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Stop TTS.lnk"); $s.TargetPath = "${CLAUDE_PLUGIN_ROOT}\tools\stop-tts.bat"; $s.WorkingDirectory = "${CLAUDE_PLUGIN_ROOT}\tools"; $s.Hotkey = "Ctrl+Alt+S"; $s.WindowStyle = 7; $s.Save()
```

## 6. Done

Tell the user setup is complete and to restart Claude Code. Remind them:
- The reader activates automatically on every response
- `/togglereader` to enable/disable
- `/setvoice` to change voice
- `Ctrl+Alt+S` to stop reading mid-sentence
