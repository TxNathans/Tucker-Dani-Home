@echo off
title Tracer Tennis
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launch.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python is not installed. Install Python 3.12 from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then double-click this file again.
  ) else (
    python launch.py %*
  )
)
echo.
pause
