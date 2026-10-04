@echo off
rem Builds the PR channel tree on an EMPTY server (first start) from games.txt
rem and writes mumo's channel map. The server must be running (start.bat).
setlocal
cd /d "%~dp0"
set PRMUMBLE_SLICE=%~dp0MumbleServer.ice
set PRMUMBLE_MUMO_INI=%~dp0mumo\mumo.ini
set PRMUMBLE_PRBF2_INI=%~dp0mumo\modules-enabled\prbf2.ini
set PRMUMBLE_GAMES=%~dp0games.txt
if not exist "mumo\modules-enabled" mkdir "mumo\modules-enabled"
"%~dp0python\python.exe" scripts\setup_channels.py %*
if errorlevel 1 (pause & exit /b 1)
echo.
echo Done. Restart mumo (close its window, run start.bat) so it loads the map.
pause
