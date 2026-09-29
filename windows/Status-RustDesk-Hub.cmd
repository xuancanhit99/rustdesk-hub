@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0..\scripts\Status.ps1" %*
exit /b %ERRORLEVEL%
