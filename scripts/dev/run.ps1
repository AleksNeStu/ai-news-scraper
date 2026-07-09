<#
.SYNOPSIS
    AI News Scraper — local dev launcher (Windows PowerShell)
.DESCRIPTION
    Brings the full stack up via docker compose: Postgres, Redis,
    ChromaDB, the one-shot Alembic + seed migration, the FastAPI app,
    and the Next.js web UI. After the stack reports healthy, prints
    the URLs the user should open.
.PARAMETER Monitor
    Also bring up Uptime Kuma (deploy-host only).
.PARAMETER Logs
    Tail logs after the stack is up (Ctrl-C to exit).
.EXAMPLE
    pwsh scripts/dev/run.ps1
.EXAMPLE
    pwsh scripts/dev/run.ps1 -Monitor
.EXAMPLE
    pwsh scripts/dev/run.ps1 -Logs
#>
param(
    [switch]$Monitor,
    [switch]$Logs,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: pwsh scripts/dev/run.ps1 [-Monitor] [-Logs] [-Help]"
    Write-Host "  -Monitor  Also bring up Uptime Kuma"
    Write-Host "  -Logs     Tail logs after stack is up"
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $ProjectRoot

# ---- preflight ----
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
    exit 1
}
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: docker daemon not running. Start Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

$composeArgs = @("-f", "docker-compose.yml")
if ($Monitor) {
    $composeArgs += @("-f", "docker-compose.monitoring.yml")
}

Write-Host "=== AI News Scraper — local dev ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"
Write-Host "Compose files: $($composeArgs -join ' ')"
Write-Host ""

# ---- bring stack up ----
Write-Host "[1/3] docker compose up -d ..." -ForegroundColor Cyan
& docker compose @composeArgs up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

# ---- wait for health ----
Write-Host "[2/3] waiting for api + web healthchecks ..." -ForegroundColor Cyan
$services = @("ai-news-api", "ai-news-web")
foreach ($svc in $services) {
    $healthy = $false
    for ($i = 0; $i -lt 60; $i++) {
        $state = docker inspect --format='{{.State.Health.Status}}' $svc 2>$null
        if ($state -eq "healthy") {
            Write-Host "  $svc : healthy"
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) {
        Write-Host "  $svc : not healthy after 60 attempts" -ForegroundColor Red
        Write-Host "  hint: pwsh scripts/dev/logs.ps1 $svc" -ForegroundColor Yellow
        exit 1
    }
}

# ---- show URLs ----
# Port matrix follows the canonical port-registry file
# (the canonical port-registry file's
# ``externalLocal.ai-news-scraper`` entry). Container ports follow framework
# defaults (Next.js=3000, FastAPI=8000); host ports are the +1
# increments from the 3800-3899 / 8000-8099 / 5433-5499 ranges
# documented in ``port-management.md``. Do not change these without
# also updating the registry, ``docker-compose.yml``, and the
# ``API_INTERNAL_URL`` / ``NEXT_PUBLIC_API_URL`` env vars.
Write-Host "[3/3] ready" -ForegroundColor Green
Write-Host ""
Write-Host "  Web UI:  http://localhost:3807"
Write-Host "  API:     http://localhost:8007"
Write-Host "  API doc: http://localhost:8007/docs"
Write-Host "  Side-ports (dev tools): postgres=5440  redis=6380  chromadb=8500"
if ($Monitor) {
    Write-Host "  Kuma:    http://127.0.0.1:3001 (deploy-host only)"
}
Write-Host "  Login:   alex@example.com / dev-only-do-not-use-in-prod"
Write-Host ""
Write-Host "  pwsh scripts/dev/stop.ps1   # stop stack"
Write-Host "  pwsh scripts/dev/logs.ps1   # tail logs"
Write-Host ""

if ($Logs) {
    & (Join-Path $ScriptDir "logs.ps1") @args
}
