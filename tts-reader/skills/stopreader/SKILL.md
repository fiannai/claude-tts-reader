---
name: stopreader
description: Stop TTS playback immediately (cross-platform stop control)
user-invocable: true
---

Stop any TTS audio that is currently playing. Run with the Bash tool.

On Linux/macOS:
```
touch ~/.tts_stop ~/.tts_skip_next; PID=$(cat ~/.tts_speak_pid 2>/dev/null); [ -n "$PID" ] && kill -TERM -- -"$PID" 2>/dev/null; pkill -x ffplay 2>/dev/null; echo stopped
```

On Windows:
```
"${CLAUDE_PLUGIN_ROOT}/tools/stop-tts.bat"
```
(Windows users also have the Ctrl+Alt+S hotkey from setup. On Windows
also create the empty file `~/.tts_skip_next` after running the bat.)

The `~/.tts_skip_next` flag makes the reader stay SILENT for this
turn's own reply — without it, the reader would immediately read your
confirmation aloud, defeating the stop.

Then reply with exactly "Stopped." and nothing else. It will appear on
screen but will not be spoken. This only stops the current playback;
it does not change the reader mode.
