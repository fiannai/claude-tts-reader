---
name: togglereader
description: Toggle the TTS reader, or set its mode (auto / manual / solo / off)
user-invocable: true
disable-model-invocation: true
---

Set the TTS reader mode. Controlled by three flag files:

| Mode | ~/.tts_disabled | ~/.tts_manual | ~/.tts_focus | Behavior |
|------|-----------------|---------------|--------------|----------|
| AUTO | absent | absent | absent | every response in every session is read aloud |
| MANUAL | absent | exists | — | silent; each response saved; read on demand |
| SOLO | absent | absent | this session's id | ONLY this session is read aloud; other sessions stay silent |
| OFF | exists | (ignored) | (ignored) | silent — but each response is still saved, so `/readlast` stays current |

If the user passed an argument, set that mode with the Bash tool:
- `auto` — delete `~/.tts_disabled`, `~/.tts_manual`, and `~/.tts_focus`
- `manual` — delete `~/.tts_disabled`, create `~/.tts_manual` (empty file)
- `solo` — claim TTS for THIS session:
  ```
  printf '%s' "$CLAUDE_CODE_SESSION_ID" > ~/.tts_focus; rm -f ~/.tts_disabled
  ```
  (Run `/togglereader solo` in a different session to move the focus there.)
- `off` — create `~/.tts_disabled` (empty file)

If no argument: toggle between OFF and the previous on-mode (create or
delete `~/.tts_disabled`; leave the other flags untouched).

In the same Bash command, `echo` the resulting mode (e.g.
`echo "reader mode: manual"`) — the tool output is the user's feedback
— and `touch ~/.tts_skip_next`.

**Then end your turn immediately with NO text at all.** TTS commands
are zero-output turns: any assistant text is a new message that
overrides the replayable last response. Say nothing.
