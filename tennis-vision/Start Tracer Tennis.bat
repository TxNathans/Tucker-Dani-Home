@echo off
setlocal
title Tracer Tennis
cd /d "%~dp0"

rem A double-click inside the zip runs from a temporary folder that Windows deletes afterwards.
set "HERE=%~dp0"
if not "%HERE:\AppData\Local\Temp\=%"=="%HERE%" goto inzip

rem Find a Python the tracking libraries support (3.13, 3.12 or 3.14). launch.py double-checks and can switch.
set "PY="
for %%V in (3.13 3.12 3.14) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  py -c "import sys" >nul 2>nul && set "PY=py"
)
if not defined PY goto nopython

%PY% launch.py %*
goto end

:nopython
echo.
echo Python is not installed on this computer. Tracer Tennis needs Python 3.13.
echo.
where winget >nul 2>nul
if errorlevel 1 goto manual
choice /c YN /m "Install Python 3.13 now"
if errorlevel 2 goto manual
winget install -e --id Python.Python.3.13 --accept-source-agreements --accept-package-agreements
echo.
echo When the install has finished, close this window and double-click Start Tracer Tennis again.
goto end

:manual
echo Install Python 3.13 from https://www.python.org/downloads/windows/
echo On the first screen of the installer, tick "Add python.exe to PATH".
echo Then double-click Start Tracer Tennis again.
goto end

:inzip
echo.
echo This is running from inside the zip file, so nothing can be saved.
echo Right-click the zip file, choose Extract All, open the folder it makes,
echo and double-click Start Tracer Tennis in there.

:end
echo.
pause
