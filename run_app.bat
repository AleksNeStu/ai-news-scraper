@echo off
:: AI News Scraper - Batch Script Launcher
:: This script launches the AI News Scraper Streamlit web application

echo Starting AI News Scraper Web Application...

:: Set working directory to script location
pushd "%~dp0"

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
