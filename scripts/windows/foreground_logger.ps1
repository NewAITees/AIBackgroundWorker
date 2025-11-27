<#
.SYNOPSIS
  Simple logger that periodically captures active windows on Windows and records them in JSONL format.

.DESCRIPTION
  - Records foreground window title/process/start time/end time at regular intervals
  - Merges consecutive same windows and writes one record when switching
  - Detects idle time and records as idle state if 60 seconds or more
  - Filters excluded processes and sensitive keywords based on privacy settings
  - Output is in JSON Lines format (one object per line)

.PARAMETER IntervalSeconds
  Sampling interval in seconds. Default: 12

.PARAMETER OutputPath
  Output file path. Default: logs/windows_foreground.jsonl next to the script

.PARAMETER StopAfterSeconds
  Exit after this many seconds (0 or less for unlimited). Default: 0

.PARAMETER PrivacyConfigPath
  Path to privacy configuration file. Default: ../config/privacy_windows.yaml

.PARAMETER IdleThreshold
  Idle detection threshold in seconds. Default: 60

.EXAMPLE
  # Record indefinitely every 12 seconds
  .\foreground_logger.ps1

.EXAMPLE
  # Record for 10 minutes only, every 5 seconds, with custom output path
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

# Get idle time in seconds
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

# Load privacy configuration
function Load-PrivacyConfig {
    param([string]$Path)

    $config = @{
        ExcludeProcesses = @('KeePass.exe', 'KeePassXC.exe', '1Password.exe', 'Bitwarden.exe', 'LastPass.exe')
        SensitiveKeywords = @('password', 'credential', 'secret', 'private')
    }

    if (-not (Test-Path $Path)) {
        Write-Host "Privacy config not found at $Path, using defaults" -ForegroundColor Yellow
        return $config
    }

    try {
        $content = Get-Content $Path -Raw

        # Extract exclude_processes section
        if ($content -match '(?s)exclude_processes:\s*\n((?:\s+-\s+.+\n?)*)') {
            $excludeList = $matches[1] -split '\n' | Where-Object { $_ -match '^\s+-\s+(.+)' } | ForEach-Object {
                $matches[1].Trim()
            }
            if ($excludeList.Count -gt 0) {
                $config.ExcludeProcesses = $excludeList
            }
        }

        # Extract sensitive_keywords section
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

# Apply privacy filter
function Test-ShouldExclude {
    param(
        [string]$ProcessName,
        [string]$WindowTitle,
        $PrivacyConfig
    )

    # Check excluded processes
    foreach ($excluded in $PrivacyConfig.ExcludeProcesses) {
        if ($ProcessName -like $excluded) {
            return $true
        }
    }

    # Check sensitive keywords
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

        # Apply privacy filter
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

# Default privacy config path
if (-not $PrivacyConfigPath) {
    $PrivacyConfigPath = Join-Path $scriptDir "..\config\privacy_windows.yaml"
}

# Default output path
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

# Load privacy configuration
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
$lastFlushTime = Get-Date
$maxFlushInterval = 300  # Force flush every 5 minutes even if window doesn't change

while ($true) {
    $now = Get-Date
    $idleSeconds = Get-IdleTime
    $isIdle = ($idleSeconds -gt $IdleThreshold)
    $info = Get-ActiveWindowInfo -PrivacyConfig $privacyConfig

    # Check if we need to force flush (periodic save)
    $timeSinceLastFlush = ($now - $lastFlushTime).TotalSeconds
    $shouldForceFlush = ($timeSinceLastFlush -ge $maxFlushInterval)

    # When window switches or idle state changes
    if ($currentInfo) {
        $windowChanged = $false
        if ($info) {
            $windowChanged = ($info.WindowTitle -ne $currentInfo.WindowTitle) -or ($info.ProcessId -ne $currentInfo.ProcessId)
        }

        $idleChanged = ($isIdle -ne $currentIsIdle)

        if ($windowChanged -or $idleChanged -or $shouldForceFlush) {
            Flush-Record -info $currentInfo -fromTime $currentStart -toTime $now -isIdle $currentIsIdle
            $recordCount++
            $lastFlushTime = $now

            $status = if ($currentIsIdle) { "[IDLE]" } else { "[ACTIVE]" }
            $statusColor = if ($currentIsIdle) { "Yellow" } else { "Green" }
            $flushReason = if ($shouldForceFlush) { " [PERIODIC]" } else { "" }
            $titlePreview = $currentInfo.WindowTitle.Substring(0, [Math]::Min(60, $currentInfo.WindowTitle.Length))
            Write-Host "[$recordCount] $status$flushReason $($currentInfo.ProcessName) - $titlePreview" -ForegroundColor $statusColor

            if ($windowChanged -or $idleChanged) {
                $currentInfo = $info
                $currentStart = $now
                $currentIsIdle = $isIdle
            } else {
                # Force flush: update start time but keep same window
                $currentStart = $now
            }
        }
    } elseif ($info) {
        # First time
        $currentInfo = $info
        $currentStart = $now
        $currentIsIdle = $isIdle
    }

    # Check stop condition
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
