<#
.SYNOPSIS
    AI News Scraper — stop local stack (Windows PowerShell)
#>
param(
    [switch]$Volumes,
    [switch]$Monitor,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: pwsh scripts/dev/stop.ps1 [-Volumes] [-Monitor] [-Help]"
    Write-Host "  -Volumes   Also wipe pgdata / redisdata / chromadata (destructive)"
    Write-Host "  -Monitor   Also stop Uptime Kuma"
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent (Split-Path -Parent $ScriptDir))

$composeArgs = @("-f", "docker-compose.yml")
if ($Monitor) { $composeArgs += @("-f", "docker-compose.monitoring.yml") }

Write-Host "=== AI News Scraper — stop stack ===" -ForegroundColor Cyan
if ($Volumes) {
    Write-Host "WARNING: -Volumes will wipe pgdata / redisdata / chromadata" -ForegroundColor Yellow
    & docker compose @composeArgs down --volumes
} else {
    & docker compose @composeArgs down
}
Write-Host "done."