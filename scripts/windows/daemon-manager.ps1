<#
.SYNOPSIS
  Windows Lifelog Daemon Manager

.DESCRIPTION
  ライフログコレクターの起動/停止/状態確認を行う管理スクリプト

.PARAMETER Action
  実行するアクション: start, stop, status, restart

.EXAMPLE
  .\daemon-manager.ps1 start
  .\daemon-manager.ps1 stop
  .\daemon-manager.ps1 status
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action
)

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$pidFile = Join-Path $scriptDir "..\lifelog_windows.pid"
$loggerScript = Join-Path $scriptDir "foreground_logger.ps1"

function Start-LifelogDaemon {
    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile
        if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
            Write-Host "Lifelog is already running (PID: $pid)" -ForegroundColor Yellow
            return
        } else {
            Remove-Item $pidFile -Force
        }
    }

    Write-Host "Starting Windows Lifelog daemon..." -ForegroundColor Green

    # PowerShellスクリプトをバックグラウンドで起動
    $process = Start-Process powershell.exe `
        -ArgumentList "-WindowStyle Hidden", "-ExecutionPolicy Bypass", "-File", "`"$loggerScript`"" `
        -PassThru `
        -WindowStyle Hidden

    $process.Id | Out-File $pidFile -Encoding ASCII

    Start-Sleep -Seconds 2

    if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
        Write-Host "Lifelog started successfully (PID: $($process.Id))" -ForegroundColor Green
        Write-Host "Log file: lifelog-system\logs\windows_foreground.jsonl" -ForegroundColor Cyan
    } else {
        Write-Host "Failed to start lifelog" -ForegroundColor Red
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
}

function Stop-LifelogDaemon {
    if (-not (Test-Path $pidFile)) {
        Write-Host "Lifelog is not running (no PID file)" -ForegroundColor Yellow
        return
    }

    $pid = Get-Content $pidFile
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue

    if (-not $process) {
        Write-Host "Lifelog is not running (stale PID file)" -ForegroundColor Yellow
        Remove-Item $pidFile -Force
        return
    }

    Write-Host "Stopping lifelog (PID: $pid)..." -ForegroundColor Yellow

    Stop-Process -Id $pid -Force
    Start-Sleep -Seconds 2

    if (-not (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
        Remove-Item $pidFile -Force
        Write-Host "Lifelog stopped successfully" -ForegroundColor Green
    } else {
        Write-Host "Failed to stop lifelog" -ForegroundColor Red
    }
}

function Get-LifelogStatus {
    if (-not (Test-Path $pidFile)) {
        Write-Host "Lifelog is not running" -ForegroundColor Yellow
        return
    }

    $pid = Get-Content $pidFile
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue

    if ($process) {
        Write-Host "Lifelog is running (PID: $pid)" -ForegroundColor Green

        # メモリ使用量
        $memMB = [math]::Round($process.WorkingSet64 / 1MB, 2)
        Write-Host "Memory usage: ${memMB} MB" -ForegroundColor Cyan

        # CPU使用率
        $cpuPercent = [math]::Round($process.CPU, 2)
        Write-Host "CPU time: ${cpuPercent}s" -ForegroundColor Cyan

        # ログファイルの最終行
        $logFile = Join-Path $scriptDir "..\logs\windows_foreground.jsonl"
        if (Test-Path $logFile) {
            $lastLine = Get-Content $logFile -Tail 1
            Write-Host "Last record:" -ForegroundColor Cyan
            Write-Host "  $lastLine" -ForegroundColor Gray
        }
    } else {
        Write-Host "Lifelog is not running (stale PID file)" -ForegroundColor Yellow
        Remove-Item $pidFile -Force
    }
}

# メイン処理
switch ($Action) {
    "start" {
        Start-LifelogDaemon
    }
    "stop" {
        Stop-LifelogDaemon
    }
    "status" {
        Get-LifelogStatus
    }
    "restart" {
        Stop-LifelogDaemon
        Start-Sleep -Seconds 3
        Start-LifelogDaemon
    }
}
