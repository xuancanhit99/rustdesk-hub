@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0..\scripts\Start.ps1" %*
exit /b %ERRORLEVEL%
