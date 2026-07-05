@echo off
REM Double-click launcher for Vaultec. Delegates to run.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
pause
