<#
.SYNOPSIS
    AI News Scraper — tail logs (Windows PowerShell)
.EXAMPLE
    pwsh scripts/dev/logs.ps1
.EXAMPLE
    pwsh scripts/dev/logs.ps1 api
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Service
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ScriptDir)

$composeArgs = @("-f", "docker-compose.yml")
if (Test-Path "docker-compose.monitoring.yml") {
    $composeArgs += @("-f", "docker-compose.monitoring.yml")
}

& docker compose @composeArgs logs -f @Service