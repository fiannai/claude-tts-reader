---
name: togglereader
description: Toggle the TTS reader on or off
user-invocable: true
disable-model-invocation: true
---

Toggle the TTS reader on or off. Check if the file ~/.tts_disabled exists.

- If it EXISTS: delete it and tell the user "Reader enabled."
- If it does NOT exist: create it (empty file) and tell the user "Reader disabled."

Use the Bash tool to check and create/delete the file. Do not explain anything else.
