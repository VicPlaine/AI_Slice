@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_windows.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ai-slice] Startup failed. Check the error above or logs in "%~dp0logs".
  pause
  exit /b %EXIT_CODE%
)

echo %* | findstr /I /C:"-StopOnly" >nul
if "%ERRORLEVEL%"=="0" exit /b 0

start "" "http://127.0.0.1:5173"
exit /b 0
