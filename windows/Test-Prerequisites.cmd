@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0Test-Prerequisites.ps1" %*
exit /b %ERRORLEVEL%
