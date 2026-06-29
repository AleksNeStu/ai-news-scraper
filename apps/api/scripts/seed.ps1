$ErrorActionPreference = "Stop"
if (-not $env:DATABASE_URL) { throw "DATABASE_URL is required" }
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f (Join-Path $scriptDir "seed.sql")
