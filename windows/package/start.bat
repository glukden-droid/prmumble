@echo off
rem Starts the Mumble server and, once its Ice port answers, mumo.
rem Close this window (or Ctrl+C) to stop mumo; stop the server from its
rem tray icon or with stop.bat.
setlocal
cd /d "%~dp0"

start "mumble-server" "%~dp0mumble-server.exe" -ini "%~dp0mumble-server.ini"

echo Waiting for the server's Ice port...
powershell -NoProfile -Command "$p=(Select-String -Path 'mumble-server.ini' -Pattern '-p\s+(\d+)').Matches[0].Groups[1].Value; for($i=0;$i -lt 30;$i++){ try { (New-Object Net.Sockets.TcpClient('127.0.0.1',[int]$p)).Close(); exit 0 } catch { Start-Sleep 1 } }; exit 1"
if errorlevel 1 (
    echo The server did not open its Ice port. See mumble-server.log
    pause
    exit /b 1
)

if not exist "mumo\modules-enabled\prbf2.ini" (
    echo No channel map yet: run setup-channels.bat once, then start.bat again.
    pause
    exit /b 0
)

cd mumo
echo Starting mumo (log: mumo\mumo.log)
"%~dp0python\python.exe" mumo.py -a -i mumo.ini
