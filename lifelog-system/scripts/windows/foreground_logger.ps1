<#
.SYNOPSIS
  Windowsでアクティブウィンドウを定期取得し、JSONLで記録する簡易ロガー。

.DESCRIPTION
  - 一定間隔でフォアグラウンドウィンドウのタイトル/プロセス/開始時刻/終了時刻を記録
  - 連続して同じウィンドウの場合は統合し、切り替わり時に1レコードを書き出す
  - アイドル時間を検出し、60秒以上でアイドル状態として記録
  - プライバシー設定に基づいて除外プロセスとセンシティブキーワードをフィルタリング
  - 出力はJSON Lines形式（1行1オブジェクト）

.PARAMETER IntervalSeconds
  取得間隔（秒）。デフォルト: 12

.PARAMETER OutputPath
  出力先パス。デフォルト: スクリプト隣の logs/windows_foreground.jsonl

.PARAMETER StopAfterSeconds
  この秒数を経過したら終了（0以下で無制限）。デフォルト: 0

.PARAMETER PrivacyConfigPath
  プライバシー設定ファイルのパス。デフォルト: ../config/privacy_windows.yaml

.PARAMETER IdleThreshold
  アイドル判定の閾値（秒）。デフォルト: 60

.EXAMPLE
  # 12秒おきに無制限で記録
  .\foreground_logger.ps1

.EXAMPLE
  # 5秒おきに10分間だけ記録し、出力先を指定
  .\foreground_logger.ps1 -IntervalSeconds 5 -StopAfterSeconds 600 -OutputPath "C:\logs\fg.jsonl"
#>

param(
    [int]$IntervalSeconds = 12,
    [string]$OutputPath = "",
    [int]$StopAfterSeconds = 0,
    [string]$PrivacyConfigPath = "",
    [int]$IdleThreshold = 60
)

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class WinApi {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

    [DllImport("kernel32.dll")]
    public static extern uint GetTickCount();

    [StructLayout(LayoutKind.Sequential)]
    public struct LASTINPUTINFO {
        public uint cbSize;
        public uint dwTime;
    }
}
"@

# アイドル時間取得（秒）
function Get-IdleTime {
    $lastInputInfo = New-Object WinApi+LASTINPUTINFO
    $lastInputInfo.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($lastInputInfo)

    if ([WinApi]::GetLastInputInfo([ref]$lastInputInfo)) {
        $tickCount = [WinApi]::GetTickCount()
        $idleMillis = $tickCount - $lastInputInfo.dwTime
        return [math]::Round($idleMillis / 1000.0, 2)
    }
    return 0
}

# プライバシー設定の読み込み
function Load-PrivacyConfig {
    param([string]$Path)

    $config = @{
        ExcludeProcesses = @('KeePass.exe', 'KeePassXC.exe', '1Password.exe', 'Bitwarden.exe', 'LastPass.exe')
        SensitiveKeywords = @('password', 'パスワード', 'credential', 'secret', 'private', '秘密')
    }

    if (-not (Test-Path $Path)) {
        Write-Host "Privacy config not found at $Path, using defaults" -ForegroundColor Yellow
        return $config
    }

    try {
        $content = Get-Content $Path -Raw

        # exclude_processesセクションを抽出
        if ($content -match '(?s)exclude_processes:\s*\n((?:\s+-\s+.+\n?)*)') {
            $excludeList = $matches[1] -split '\n' | Where-Object { $_ -match '^\s+-\s+(.+)' } | ForEach-Object {
                $matches[1].Trim()
            }
            if ($excludeList.Count -gt 0) {
                $config.ExcludeProcesses = $excludeList
            }
        }

        # sensitive_keywordsセクションを抽出
        if ($content -match '(?s)sensitive_keywords:\s*\n((?:\s+-\s+.+\n?)*)') {
            $keywordList = $matches[1] -split '\n' | Where-Object { $_ -match '^\s+-\s+(.+)' } | ForEach-Object {
                $matches[1].Trim()
            }
            if ($keywordList.Count -gt 0) {
                $config.SensitiveKeywords = $keywordList
            }
        }

        Write-Host "Loaded privacy config from $Path" -ForegroundColor Green
    } catch {
        Write-Warning "Failed to parse privacy config: $_"
    }

    return $config
}

# プライバシーフィルターを適用
function Test-ShouldExclude {
    param(
        [string]$ProcessName,
        [string]$WindowTitle,
        $PrivacyConfig
    )

    # 除外プロセスチェック
    foreach ($excluded in $PrivacyConfig.ExcludeProcesses) {
        if ($ProcessName -like $excluded) {
            return $true
        }
    }

    # センシティブキーワードチェック
    foreach ($keyword in $PrivacyConfig.SensitiveKeywords) {
        if ($WindowTitle -like "*$keyword*" -or $ProcessName -like "*$keyword*") {
            return $true
        }
    }

    return $false
}

function Get-ActiveWindowInfo {
    param($PrivacyConfig)

    $hWnd = [WinApi]::GetForegroundWindow()
    if ($hWnd -eq [IntPtr]::Zero) { return $null }

    $sb = New-Object System.Text.StringBuilder 1024
    [void][WinApi]::GetWindowText($hWnd, $sb, $sb.Capacity)
    $title = $sb.ToString()

    [uint32]$procId = 0
    [void][WinApi]::GetWindowThreadProcessId($hWnd, [ref]$procId)

    try {
        $proc = Get-Process -Id $procId -ErrorAction Stop
        $exe = $proc.Path
        $name = $proc.ProcessName

        # プライバシーフィルター
        if (Test-ShouldExclude -ProcessName $name -WindowTitle $title -PrivacyConfig $PrivacyConfig) {
            return $null
        }
    } catch {
        $exe = ""
        $name = ""
    }

    return [PSCustomObject]@{
        WindowTitle = $title
        ProcessId   = $procId
        ProcessName = $name
        ExePath     = $exe
    }
}

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent

# プライバシー設定パスのデフォルト値
if (-not $PrivacyConfigPath) {
    $PrivacyConfigPath = Join-Path $scriptDir "..\config\privacy_windows.yaml"
}

# 出力パスのデフォルト値
if (-not $OutputPath) {
    $defaultDir = Join-Path $scriptDir "..\logs"
    if (-not (Test-Path $defaultDir)) {
        New-Item -ItemType Directory -Path $defaultDir -Force | Out-Null
    }
    $resolved = Resolve-Path $defaultDir
    $OutputPath = Join-Path $resolved "windows_foreground.jsonl"
} else {
    $outDir = Split-Path $OutputPath -Parent
    if (-not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
}

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "Windows Lifelog Foreground Logger" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Sampling interval: ${IntervalSeconds}s" -ForegroundColor Green
Write-Host "Idle threshold: ${IdleThreshold}s" -ForegroundColor Green
Write-Host "Output: $OutputPath" -ForegroundColor Green
if ($StopAfterSeconds -gt 0) {
    Write-Host "Duration: ${StopAfterSeconds}s" -ForegroundColor Yellow
}
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# プライバシー設定読み込み
$privacyConfig = Load-PrivacyConfig -Path $PrivacyConfigPath
Write-Host "Privacy filters:" -ForegroundColor Green
Write-Host "  Excluded processes: $($privacyConfig.ExcludeProcesses.Count)" -ForegroundColor Green
Write-Host "  Sensitive keywords: $($privacyConfig.SensitiveKeywords.Count)" -ForegroundColor Green
Write-Host ""

$last = $null
$startedAt = Get-Date
$stopAt = $null
if ($StopAfterSeconds -gt 0) {
    $stopAt = (Get-Date).AddSeconds($StopAfterSeconds)
}

function Flush-Record($info, $fromTime, $toTime, $isIdle) {
    if (-not $info) { return }
    $obj = [PSCustomObject]@{
        start         = $fromTime.ToString("o")
        end           = $toTime.ToString("o")
        duration_sec  = [int]($toTime - $fromTime).TotalSeconds
        window_title  = $info.WindowTitle
        process_id    = $info.ProcessId
        process_name  = $info.ProcessName
        exe_path      = $info.ExePath
        is_idle       = $isIdle
    }
    $json = $obj | ConvertTo-Json -Compress
    Add-Content -Path $OutputPath -Value $json
}

$currentInfo = $null
$currentStart = Get-Date
$currentIsIdle = $false
$recordCount = 0

while ($true) {
    $now = Get-Date
    $idleSeconds = Get-IdleTime
    $isIdle = ($idleSeconds -gt $IdleThreshold)
    $info = Get-ActiveWindowInfo -PrivacyConfig $privacyConfig

    # ウィンドウが切り替わったか、アイドル状態が変化した場合
    if ($currentInfo) {
        $windowChanged = $false
        if ($info) {
            $windowChanged = ($info.WindowTitle -ne $currentInfo.WindowTitle) -or ($info.ProcessId -ne $currentInfo.ProcessId)
        }

        $idleChanged = ($isIdle -ne $currentIsIdle)

        if ($windowChanged -or $idleChanged) {
            Flush-Record -info $currentInfo -fromTime $currentStart -toTime $now -isIdle $currentIsIdle
            $recordCount++

            $status = if ($currentIsIdle) { "[IDLE]" } else { "[ACTIVE]" }
            $statusColor = if ($currentIsIdle) { "Yellow" } else { "Green" }
            $titlePreview = $currentInfo.WindowTitle.Substring(0, [Math]::Min(60, $currentInfo.WindowTitle.Length))
            Write-Host "[$recordCount] $status $($currentInfo.ProcessName) - $titlePreview" -ForegroundColor $statusColor

            $currentInfo = $info
            $currentStart = $now
            $currentIsIdle = $isIdle
        }
    } elseif ($info) {
        # 初回
        $currentInfo = $info
        $currentStart = $now
        $currentIsIdle = $isIdle
    }

    # 停止チェック
    if ($stopAt -and $now -ge $stopAt) {
        if ($currentInfo) {
            Flush-Record -info $currentInfo -fromTime $currentStart -toTime $now -isIdle $currentIsIdle
            $recordCount++
        }
        break
    }

    Start-Sleep -Seconds $IntervalSeconds
}

Write-Host ""
Write-Host "Foreground logger stopped." -ForegroundColor Cyan
Write-Host "Total records: $recordCount" -ForegroundColor Green
