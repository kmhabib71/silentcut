@echo off
echo Running FFmpeg installation with admin rights...
powershell -Command "Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0install_ffmpeg.ps1\"' -Verb RunAs"
echo.
echo If a User Account Control prompt appears, please click Yes to allow the installation.
echo.
echo After installation is complete, please restart any applications that use FFmpeg.
pause 