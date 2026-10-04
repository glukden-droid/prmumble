@echo off
rem Lets a bot enter, listen, speak and mute/deafen in every channel.
rem The bot must be connected with a client certificate:  grant-bot.bat BotName
setlocal
cd /d "%~dp0"
if "%~1"=="" (echo usage: grant-bot.bat ^<bot name^> & exit /b 1)
set PRMUMBLE_SLICE=%~dp0MumbleServer.ice
set PRMUMBLE_MUMO_INI=%~dp0mumo\mumo.ini
"%~dp0python\python.exe" scripts\grant_bot.py %1
