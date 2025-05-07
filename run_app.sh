#!/bin/bash
# AI News Scraper - Shell Script Launcher
# This script launches the AI News Scraper Streamlit web application

# Print welcome message
echo "Starting AI News Scraper Web Application..."

# Set script directory as working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is installed
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if .venv directory exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Warning: Could not activate virtual environment. Will try to use system Python."
    fi
fi

# Check if Poetry is installed and set up
if command -v poetry &> /dev/null; then
    echo "Poetry found, installing dependencies if needed..."
    poetry install --no-interaction --no-ansi
    if [ $? -eq 0 ]; then
        echo "Launching application using Poetry..."
        # The -- passes all remaining arguments to the script
        poetry run streamlit run src/ui/app.py
        exit $?
    else
        echo "Warning: Poetry install failed. Falling back to pip..."
    fi
fi

# If Poetry not available or failed, try pip
echo "Installing dependencies with pip..."
$PYTHON -m pip install -r requirements.txt

echo "Starting Streamlit application..."
$PYTHON -m streamlit run src/ui/app.py

# Exit with the exit code from Streamlit
exit $?
