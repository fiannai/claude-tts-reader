---
name: tts-setup
description: First-time setup for Claude TTS Reader — configure server, API key, voice, and hotkey
user-invocable: true
disable-model-invocation: true
---

Run first-time setup for Claude TTS Reader.

## 1. Check prerequisites

Run these checks and report results:
- Python 3 is available (`python3` or `python`)
- `ffplay` is available (part of FFmpeg)
- Python `requests` library is installed

If `requests` is missing, offer to install it with `pip install requests`.
If `ffplay` is missing, tell the user to install FFmpeg.

## 2. Configure TTS server

Ask the user for their TTS server URL (default: `http://waternoose:8765` — the AI-server manager; a direct Kokoro server also works, e.g. `http://localhost:8190` with `tts_path` set to `/api/generate`).

Test the connection with a tiny synthesize request:
`curl -s -o /dev/null -w '%{http_code}' -X POST <url><tts_path> -H "Content-Type: application/json" -d '{"text":"test"}'`
Expect 200 (or 401/403 if the server enforces auth — that's fine, the key comes next). If it fails, warn but continue.

## 3. API key

Ask the user for their TTS API key (issued by the manager). Write it to `~/.tts_api_key` with owner-only permissions (mode 600 on Linux/macOS). If they don't have one, skip — the reader sends no auth header when the key file is absent.

Never write the key into `tts-config.json` or any file inside the plugin/repo.

## 4. Choose a voice

Show available voices and ask the user to pick one:
- Female: af_heart, af_bella, af_nicole, af_sarah, af_sky
- Male: am_adam, am_michael, am_echo, am_onyx

Default is af_heart.

## 5. Write config

Write the config to `${CLAUDE_PLUGIN_ROOT}/tools/tts-config.json`:
```json
{
  "api_url": "<user's url>",
  "tts_path": "/v1/tts/synthesize",
  "api_key_file": "~/.tts_api_key",
  "default_voice": "<user's choice>",
  "max_queue_size": 20,
  "request_timeout": 30,
  "sentence_pause_min_ms": 80,
  "sentence_pause_max_ms": 120,
  "batch_start_percent": 25
}
```

Also write the voice to `~/.tts_voice`.

## 6. Register Ctrl+Alt+S hotkey (Windows only)

On Windows, run this PowerShell to create a global hotkey:
```powershell
$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Stop TTS.lnk"); $s.TargetPath = "${CLAUDE_PLUGIN_ROOT}\tools\stop-tts.bat"; $s.WorkingDirectory = "${CLAUDE_PLUGIN_ROOT}\tools"; $s.Hotkey = "Ctrl+Alt+S"; $s.WindowStyle = 7; $s.Save()
```

## 7. Done

Tell the user setup is complete and to restart Claude Code. Remind them:
- The reader activates automatically on every response
- `/togglereader` to enable/disable
- `/setvoice` to change voice
- `Ctrl+Alt+S` to stop reading mid-sentence (Windows)
- Failures are logged to `~/tts_hook_debug.log`
