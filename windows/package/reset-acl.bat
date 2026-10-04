@echo off
rem Puts the channel rights (ACL) and team links back to what
rem setup-channels.bat sets, keeping channels, registrations, admins, bots.
rem Restart mumo afterwards (close the start.bat window, run start.bat).
setlocal
cd /d "%~dp0"
set PRMUMBLE_SLICE=%~dp0MumbleServer.ice
set PRMUMBLE_MUMO_INI=%~dp0mumo\mumo.ini
set PRMUMBLE_PRBF2_INI=%~dp0mumo\modules-enabled\prbf2.ini
"%~dp0python\python.exe" scripts\reset_acl.py %*
