@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0asr-cli.ps1" -Format srt -Lang ja %*
pause