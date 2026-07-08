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

**Then end your turn immediately with NO text at all.** TTS commands
are zero-output turns: never reply "Reading.", never confirm, never
summarize — any assistant text is a new message and violates the rule
that these commands stay silent. The tool's own output line is the only
feedback. The `~/.tts_skip_next` flag is insurance in case text is ever
emitted anyway (it keeps such a turn out of the speakers and out of the
replay slots).

Do not paste or echo the message content into the command — the whole
point is that the text is never re-sent.
