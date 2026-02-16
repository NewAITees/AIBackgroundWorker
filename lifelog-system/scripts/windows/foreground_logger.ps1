<#
.SYNOPSIS
  Compatibility wrapper for scripts/windows/foreground_logger.ps1
#>

$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$rootScript = Join-Path $scriptDir "..\..\..\scripts\windows\foreground_logger.ps1"

if (-not (Test-Path $rootScript)) {
    Write-Error "root script not found: $rootScript"
    exit 1
}

& $rootScript @args
exit $LASTEXITCODE
