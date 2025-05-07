#!/bin/bash
# AI News Scraper - Shell Script Launcher
# This script launches the AI News Scraper Streamlit web application

# Set project root directory as working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"
cd "$PROJECT_ROOT"

# Print welcome message with version information
echo "Starting AI News Scraper Web Application..."

# Check if git is available and the directory is a git repository
if command -v git &> /dev/null && git rev-parse --is-inside-work-tree &> /dev/null; then
    echo "----------------------------------------"
    echo "📋 Version Information:"
    echo "----------------------------------------"
    COMMIT_HASH=$(git rev-parse --short HEAD)
    COMMIT_DATE=$(git log -1 --format="%cd" --date=format:"%Y-%m-%d %H:%M:%S")
    COMMIT_SUBJECT=$(git log -1 --format="%s")
    BRANCH=$(git branch --show-current)
    
    echo "🔖 Commit: ${COMMIT_HASH}"
    echo "📅 Date: ${COMMIT_DATE}"
    echo "📌 Branch: ${BRANCH}"
    echo "🔍 Message: ${COMMIT_SUBJECT}"
    
    # Try to get repository URL
    if REPO_URL=$(git config --get remote.origin.url 2>/dev/null); then
        # Remove .git suffix if present
        REPO_URL=${REPO_URL%.git}
        
        # Convert SSH URL to HTTPS if needed
        if [[ $REPO_URL == git@* ]]; then
            # Extract domain and path from SSH URL (git@github.com:username/repo)
            DOMAIN=$(echo $REPO_URL | cut -d@ -f2 | cut -d: -f1)
            PATH_PART=$(echo $REPO_URL | cut -d: -f2)
            REPO_URL="https://${DOMAIN}/${PATH_PART}"
        fi
        
        echo "🌐 Repository: ${REPO_URL}"
    else
        echo "🌐 Repository: Unknown"
    fi
    
    echo "----------------------------------------"
else
    echo "Git not available or not a git repository - version information unavailable"
fi

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
