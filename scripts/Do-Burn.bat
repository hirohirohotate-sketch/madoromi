@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0subs-burn-cli.ps1" %*
pause