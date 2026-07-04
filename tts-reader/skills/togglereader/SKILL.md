---
name: togglereader
description: Toggle the TTS reader, or set its mode (auto / manual / off)
user-invocable: true
disable-model-invocation: true
---

Set the TTS reader mode. Three modes, controlled by two flag files:

| Mode | ~/.tts_disabled | ~/.tts_manual | Behavior |
|------|-----------------|---------------|----------|
| AUTO | absent | absent | every response is read aloud |
| MANUAL | absent | exists | silent; each response is saved; read on demand |
| OFF | exists | (ignored) | nothing happens |

If the user passed an argument, set that mode with the Bash tool:
- `auto` — delete `~/.tts_disabled` and `~/.tts_manual`
- `manual` — delete `~/.tts_disabled`, create `~/.tts_manual` (empty file)
- `off` — create `~/.tts_disabled` (empty file)

If no argument: toggle between OFF and the previous on-mode (create or
delete `~/.tts_disabled`; leave `~/.tts_manual` untouched).

Tell the user the resulting mode in one short sentence. In MANUAL mode,
also remind them: say "read that" (or run `/readlast`) and the last
response is read aloud via:

```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/read-last.py"
```

Do not explain anything else.
