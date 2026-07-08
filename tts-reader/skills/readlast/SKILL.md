---
name: readlast
description: Read the last assistant response aloud (manual-mode trigger — also works as "read that again")
user-invocable: true
---

Read the last saved assistant response aloud. Run with the Bash tool:

```
{ python3 "${CLAUDE_PLUGIN_ROOT}/tools/read-last.py" || python "${CLAUDE_PLUGIN_ROOT}/tools/read-last.py"; } && touch ~/.tts_skip_next
```

The tool reads THIS session's last saved response (the Stop hook keeps
a per-session slot; other concurrent sessions and spawned workers can't
clobber it) and hands playback off in the background — pass it nothing.
It falls back to the global `~/.tts_last_message` only when no
per-session slot exists. If it reports no saved message yet, tell the
user a response has to finish first before it can be replayed.

Then reply with exactly "Reading." and nothing else — a completely
empty reply is not possible (the runtime rejects empty turns), so this
fixed token is the minimum. The `~/.tts_skip_next` flag in the command
keeps it out of the speakers and out of the replay slots: repeating
/readlast still replays the real content, never "Reading."

Do not paste or echo the message content into the command — the whole
point is that the text is never re-sent.
