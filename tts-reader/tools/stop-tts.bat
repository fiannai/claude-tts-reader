@echo off
echo. > "%USERPROFILE%\.tts_stop"
taskkill /F /IM ffplay.exe >nul 2>&1
