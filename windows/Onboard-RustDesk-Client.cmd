@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0..\client\Onboard.ps1" %*
exit /b %ERRORLEVEL%
