# AI News Scraper - PowerShell Script Launcher
# This script launches the AI News Scraper Streamlit web application

# Set project root as working directory (parent of scripts directory)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location -Path $projectRoot

Write-Host "Starting AI News Scraper Web Application..." -ForegroundColor Cyan

# Check if git is available and display version information
try {
    $gitCheck = git rev-parse --is-inside-work-tree 2>$null
    if ($gitCheck -eq "true") {
        Write-Host "----------------------------------------" -ForegroundColor Blue
        Write-Host "📋 Version Information:" -ForegroundColor Green
        Write-Host "----------------------------------------" -ForegroundColor Blue

        $commitHash = git rev-parse --short HEAD
        $commitDate = git log -1 --format="%cd" --date=format:"%Y-%m-%d %H:%M:%S"
        $commitSubject = git log -1 --format="%s"
        $branch = git branch --show-current

        Write-Host "🔖 Commit: $commitHash" -ForegroundColor Yellow
        Write-Host "📅 Date: $commitDate" -ForegroundColor Yellow
        Write-Host "📌 Branch: $branch" -ForegroundColor Yellow
        Write-Host "🔍 Message: $commitSubject" -ForegroundColor Yellow
        
        # Try to get repository URL
        try {
            $repoUrl = git config --get remote.origin.url 2>$null
            
            # Format the URL for display
            if ($repoUrl -ne $null) {
                # Remove .git suffix if present
                if ($repoUrl.EndsWith(".git")) {
                    $repoUrl = $repoUrl.Substring(0, $repoUrl.Length - 4)
                }
                
                # Convert SSH URL to HTTPS if needed
                if ($repoUrl.StartsWith("git@")) {
                    # Example: git@github.com:username/repo -> https://github.com/username/repo
                    $parts = $repoUrl.Split(':')
                    if ($parts.Length -eq 2) {
                        $domain = $parts[0].Split('@')[1]
                        $path = $parts[1]
                        $repoUrl = "https://$domain/$path"
                    }
                }
                
                Write-Host "🌐 Repository: $repoUrl" -ForegroundColor Yellow
            } else {
                Write-Host "🌐 Repository: Unknown" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "🌐 Repository: Unknown" -ForegroundColor Yellow
        }
        
        Write-Host "----------------------------------------" -ForegroundColor Blue
    }
    else {
        Write-Host "Not a git repository - version information unavailable" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Git not available or not a git repository - version information unavailable" -ForegroundColor Yellow
}

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
