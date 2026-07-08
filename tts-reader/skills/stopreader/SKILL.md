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

**Then end your turn immediately with NO text at all.** TTS commands
are zero-output turns: never reply "Stopped.", never confirm — any
assistant text is a new message and violates the rule that these
commands stay silent. The command's own `stopped` echo is the only
feedback. The `~/.tts_skip_next` flag is insurance in case text is ever
emitted anyway. This only stops the current playback; it does not
change the reader mode.
