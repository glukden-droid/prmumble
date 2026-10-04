@echo off
rem Cross-team local voice (enemies nearby hear normal speech):
rem   link-teams.bat status
rem   link-teams.bat on  [main0 ...]    no name = every game server
rem   link-teams.bat off [main0 ...]
setlocal
cd /d "%~dp0"
if "%~1"=="" (echo usage: link-teams.bat status ^| on [game ...] ^| off [game ...] & exit /b 1)
set PRMUMBLE_SLICE=%~dp0MumbleServer.ice
set PRMUMBLE_MUMO_INI=%~dp0mumo\mumo.ini
set PRMUMBLE_PRBF2_INI=%~dp0mumo\modules-enabled\prbf2.ini
"%~dp0python\python.exe" scripts\link_teams.py %*
