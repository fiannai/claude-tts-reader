---
name: stopreader
description: Stop TTS playback immediately (cross-platform stop control)
user-invocable: true
---

Stop any TTS audio that is currently playing. Run with the Bash tool.

On Linux/macOS:
```
touch ~/.tts_stop; PID=$(cat ~/.tts_speak_pid 2>/dev/null); [ -n "$PID" ] && kill -TERM -- -"$PID" 2>/dev/null; pkill -x ffplay 2>/dev/null; echo stopped
```

On Windows:
```
"${CLAUDE_PLUGIN_ROOT}/tools/stop-tts.bat"
```
(Windows users also have the Ctrl+Alt+S hotkey from setup.)

Then tell the user "Stopped." — nothing else. This only stops the
current playback; it does not change the reader mode.
