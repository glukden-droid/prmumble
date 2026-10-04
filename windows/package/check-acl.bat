@echo off
rem Effective permissions of connected players:  check-acl.bat [part of nick]
setlocal
cd /d "%~dp0"
set PRMUMBLE_SLICE=%~dp0MumbleServer.ice
set PRMUMBLE_MUMO_INI=%~dp0mumo\mumo.ini
"%~dp0python\python.exe" scripts\check_acl.py %*
