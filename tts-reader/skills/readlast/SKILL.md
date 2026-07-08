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

The `~/.tts_skip_next` flag is essential: without it, your own
confirmation reply gets read aloud on turn end — killing the very
replay the user asked for — and would overwrite the saved message.

Then reply with exactly "Reading." and nothing else. It shows on
screen but is not spoken and does not replace the saved message.

Do not paste or echo the message content into the command — the whole
point is that the text is never re-sent.
