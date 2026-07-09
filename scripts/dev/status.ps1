<#
.SYNOPSIS
    AI News Scraper — show stack status (Windows PowerShell)
#>
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent (Split-Path -Parent $ScriptDir))

$composeArgs = @("-f", "docker-compose.yml")
if (Test-Path "docker-compose.monitoring.yml") {
    $composeArgs += @("-f", "docker-compose.monitoring.yml")
}

Write-Host "=== containers ===" -ForegroundColor Cyan
& docker compose @composeArgs ps
Write-Host ""
Write-Host "=== health states ===" -ForegroundColor Cyan
docker ps --filter "name=ai-news-" --format "{{.Names}}	{{.Status}}"
Write-Host ""
Write-Host "=== urls (when healthy) ===" -ForegroundColor Cyan
# Per the canonical port-registry file's externalLocal.ai-news-scraper entry.
Write-Host "  Web UI:  http://localhost:3807"
Write-Host "  API:     http://localhost:8007"
Write-Host "  API doc: http://localhost:8007/docs"
