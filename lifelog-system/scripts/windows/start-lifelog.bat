@echo off
REM Compatibility wrapper for scripts/windows/start-lifelog.bat

set SCRIPT_DIR=%~dp0
set ROOT_BAT=%SCRIPT_DIR%..\..\..\scripts\windows\start-lifelog.bat

if not exist "%ROOT_BAT%" (
  echo root script not found: %ROOT_BAT%
  exit /b 1
)

call "%ROOT_BAT%" %*
exit /b %ERRORLEVEL%
