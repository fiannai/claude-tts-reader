---
name: setvoice
description: Change the TTS voice used by the reader
user-invocable: true
disable-model-invocation: true
---

Change the TTS voice used by the reader. The user may provide a voice name as an argument: $ARGUMENTS

If a voice name was provided, write it to ~/.tts_voice and confirm: "Voice set to [name]."

If no voice name was provided, read the current voice from ~/.tts_voice (default is af_heart if file doesn't exist), then list these available Kokoro voices and ask the user to pick one:

Female: af_heart, af_bella, af_nicole, af_sarah, af_sky
Male: am_adam, am_michael, am_echo, am_onyx

Use the Bash tool to read/write ~/.tts_voice. Keep the response brief.
