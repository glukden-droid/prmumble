@echo off
rem Stops mumo and the Mumble server started by start.bat.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*mumo.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
taskkill /im mumble-server.exe >nul 2>&1
echo Stopped.
