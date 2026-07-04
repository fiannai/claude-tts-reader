@echo off
echo. > "%USERPROFILE%\.tts_stop"
if exist "%USERPROFILE%\.tts_speak_pid" (
    for /f %%i in (%USERPROFILE%\.tts_speak_pid) do taskkill /F /T /PID %%i >nul 2>&1
)
taskkill /F /IM ffplay.exe >nul 2>&1
