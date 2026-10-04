@echo off
rem Sets the SuperUser password:  set-superuser-password.bat NewPassword
setlocal
cd /d "%~dp0"
if "%~1"=="" (echo usage: set-superuser-password.bat ^<password^> & exit /b 1)
"%~dp0mumble-server.exe" -ini "%~dp0mumble-server.ini" -supw %1
