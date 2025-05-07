# AI News Scraper - PowerShell Script Launcher
# This script launches the AI News Scraper Streamlit web application

Write-Host "Starting AI News Scraper Web Application..." -ForegroundColor Cyan

# Set script directory as working directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $scriptPath

# Check if Python is installed
try {
    $pythonVersion = (python --version 2>&1)
    $pythonCmd = "python"
}
catch {
    try {
        $pythonVersion = (python3 --version 2>&1)
        $pythonCmd = "python3"
    }
    catch {
        Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
        Read-Host -Prompt "Press Enter to exit"
        exit 1
    }
}

Write-Host "Found $pythonVersion" -ForegroundColor Green

# Check if virtual environment exists and activate it
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    try {
        & ".venv\Scripts\Activate.ps1"
    }
    catch {
        Write-Host "Warning: Could not activate virtual environment. Will try to use system Python." -ForegroundColor Yellow
    }
}
elseif (Test-Path ".venv\bin\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    try {
        & ".venv\bin\Activate.ps1"
    }
    catch {
        Write-Host "Warning: Could not activate virtual environment. Will try to use system Python." -ForegroundColor Yellow
    }
}

# Check if Poetry is installed
try {
    $poetryVersion = (poetry --version 2>&1)
    Write-Host "$poetryVersion found, installing dependencies if needed..." -ForegroundColor Green
    
    poetry install
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Launching application using Poetry..." -ForegroundColor Green
        poetry run streamlit run src\ui\app.py
        exit $LASTEXITCODE
    }
    else {
        Write-Host "Warning: Poetry install failed. Falling back to pip..." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Poetry not found, using pip instead..." -ForegroundColor Yellow
}

# If Poetry not available or failed, try pip
Write-Host "Installing dependencies with pip..." -ForegroundColor Cyan
& $pythonCmd -m pip install -r requirements.txt

# Start the application
Write-Host "Starting Streamlit application..." -ForegroundColor Green
& $pythonCmd -m streamlit run src\ui\app.py

# Exit with the exit code from Streamlit
exit $LASTEXITCODE
