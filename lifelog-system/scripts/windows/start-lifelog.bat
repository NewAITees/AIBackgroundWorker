@echo off
REM Windows Lifelog起動バッチファイル（タスクスケジューラ用）

REM スクリプトのディレクトリを取得
set SCRIPT_DIR=%~dp0

REM PowerShellスクリプトをバックグラウンドで起動（ウィンドウ非表示）
powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SCRIPT_DIR%foreground_logger.ps1"

exit /b 0
