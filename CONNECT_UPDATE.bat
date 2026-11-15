@echo off
cd /d "%~dp0"
if not exist "START.bat" (
  echo Copy CONNECT_UPDATE.bat into your installed PeakWatch folder first.
  pause
  exit /b 1
)
if not exist "panels.py" (
  echo This connector requires PeakWatch v0.3 or later. Install v0.3 first.
  pause
  exit /b 1
)
echo Close all running PeakWatch windows before continuing.
pause
powershell -NoProfile -Command "$d=Join-Path $env:LOCALAPPDATA 'PeakWatch'; New-Item -ItemType Directory -Force -Path $d | Out-Null; $cfg=[ordered]@{manifest_url='https://raw.githubusercontent.com/AlphaDragona3/peakwatch-updates/main/manifest.json';automatic=$true}; $cfg | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $d 'update_settings.json') -Encoding Ascii"
if errorlevel 1 (
  echo Failed to save update settings.
  pause
  exit /b 1
)
echo Update URL configured. Starting PeakWatch.
call START.bat
