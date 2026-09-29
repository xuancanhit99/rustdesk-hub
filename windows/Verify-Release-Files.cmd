@echo off
setlocal
powershell.exe -NoLogo -NoProfile -File "%~dp0Verify-ReleaseFiles.ps1" %*
exit /b %ERRORLEVEL%
