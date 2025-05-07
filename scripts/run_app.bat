@echo off
:: AI News Scraper - Batch Script Launcher
:: This script launches the AI News Scraper Streamlit web application

:: Enable delayed expansion for variables inside loops
setlocal enabledelayedexpansion

:: Set working directory to project root (parent of scripts directory)
pushd "%~dp0\.."

echo Starting AI News Scraper Web Application...

:: Check if git is available and display version information
where git >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    git rev-parse --is-inside-work-tree >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo ----------------------------------------
        echo 📋 Version Information:
        echo ----------------------------------------
        
        for /f "tokens=*" %%g in ('git rev-parse --short HEAD') do set COMMIT_HASH=%%g
        for /f "tokens=*" %%g in ('git log -1 --format^=%%cd --date^=format:"%%Y-%%m-%%d %%H:%%M:%%S"') do set COMMIT_DATE=%%g
        for /f "tokens=*" %%g in ('git log -1 --format^=%%s') do set COMMIT_SUBJECT=%%g
        for /f "tokens=*" %%g in ('git branch --show-current') do set BRANCH=%%g
        
        echo 🔖 Commit: %COMMIT_HASH%
        echo 📅 Date: %COMMIT_DATE%
        echo 📌 Branch: %BRANCH%
        echo 🔍 Message: %COMMIT_SUBJECT%
        
        :: Try to get repository URL
        for /f "tokens=*" %%g in ('git config --get remote.origin.url 2^>nul') do set REPO_URL=%%g
        if defined REPO_URL (
            :: Remove .git suffix if present
            if "!REPO_URL:~-4!" == ".git" set REPO_URL=!REPO_URL:~0,-4!
            
            :: Check if it's an SSH URL and convert to HTTPS if needed
            if "!REPO_URL:~0,4!" == "git@" (
                for /f "tokens=1,2 delims=:" %%a in ("!REPO_URL!") do (
                    set DOMAIN=%%a
                    set PATH_PART=%%b
                    set DOMAIN=!DOMAIN:~4!
                    set REPO_URL=https://!DOMAIN!/!PATH_PART!
                )
            )
            
            echo 🌐 Repository: !REPO_URL!
        ) else (
            echo 🌐 Repository: Unknown
        )
        
        echo ----------------------------------------
    ) else (
        echo Not a git repository - version information unavailable
    )
) else (
    echo Git not available - version information unavailable
)

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if virtual environment exists and activate it
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else if exist .venv\bin\activate (
    echo Activating virtual environment...
    call .venv\bin\activate
)

:: Check if Poetry is installed
where poetry >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Poetry found, installing dependencies if needed...
    poetry install 
    if %ERRORLEVEL% EQU 0 (
        echo Launching application using Poetry...
        poetry run streamlit run src\ui\app.py
        exit /b %ERRORLEVEL%
    ) else (
        echo Warning: Poetry install failed. Falling back to pip...
    )
)

:: If Poetry not available or failed, try pip
echo Installing dependencies with pip...
python -m pip install -r requirements.txt

:: Start the application
echo Starting Streamlit application...
python -m streamlit run src\ui\app.py

:: Exit with the exit code from Streamlit
exit /b %ERRORLEVEL%
