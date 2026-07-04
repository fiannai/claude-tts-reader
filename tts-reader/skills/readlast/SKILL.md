---
name: readlast
description: Read the last assistant response aloud (manual-mode trigger — also works as "read that again")
user-invocable: true
---

Read the last saved assistant response aloud. Run with the Bash tool:

```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/read-last.py" || python "${CLAUDE_PLUGIN_ROOT}/tools/read-last.py"
```

The tool reads the text saved by the Stop hook (`~/.tts_last_message`)
and hands playback off in the background — pass it nothing. If it
reports no saved message yet, tell the user a response has to finish
first before it can be replayed.

Do not paste or echo the message content into the command — the whole
point is that the text is never re-sent.
