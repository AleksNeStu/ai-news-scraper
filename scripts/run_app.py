#!/usr/bin/env python
# filepath: /home/he/Projects/ai-news-scraper/run_app.py
"""
Universal launcher script for the AI News Scraper application.
This script works on all platforms (Windows, macOS, Linux).
"""

import os
import sys
import subprocess
import argparse
import platform
from pathlib import Path

# Determine the script's directory and project root
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent


def print_version_info():
    """Print version information from git if available."""
    try:
        # Check if in a git repository
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], 
                               stderr=subprocess.DEVNULL)
        
        print("----------------------------------------")
        print("📋 Version Information:")
        print("----------------------------------------")
        
        # Get commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            text=True
        ).strip()
        print(f"🔖 Commit: {commit_hash}")
        
        # Get commit date
        commit_date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M:%S"], 
            text=True
        ).strip()
        print(f"📅 Date: {commit_date}")
        
        # Get current branch
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], 
            text=True
        ).strip()
        print(f"📌 Branch: {branch}")
        
        # Get commit subject
        commit_subject = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], 
            text=True
        ).strip()
        print(f"🔍 Message: {commit_subject}")
        
        # Get repository URL
        try:
            repo_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            # Format URL for display
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
            
            # Convert SSH URL to HTTPS format if needed
            if repo_url.startswith('git@'):
                parts = repo_url.split(':')
                if len(parts) == 2:
                    domain = parts[0].split('@')[1]
                    path = parts[1]
                    repo_url = f"https://{domain}/{path}"
                    
            print(f"🌐 Repository: {repo_url}")
        except (subprocess.SubprocessError, FileNotFoundError):
            print("🌐 Repository: Unknown")
            
        print("----------------------------------------")
        
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Git not available or not a git repository - version information unavailable")


def check_python():
    """Check if Python is installed and with correct version."""
    version_info = sys.version_info
    if version_info.major < 3 or (version_info.major == 3 and version_info.minor < 9):
        print(f"Error: Python 3.9+ is required. Found Python {version_info.major}.{version_info.minor}")
        return False
    return True


def setup_virtualenv():
    """Set up virtual environment if it doesn't exist."""
    venv_dir = PROJECT_ROOT / "venv"
    venv_python = venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
    
    # Check if venv exists
    if not venv_dir.exists():
        print("Creating virtual environment...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            print("Virtual environment created successfully.")
        except subprocess.CalledProcessError:
            print("Error creating virtual environment.")
            return False
    
    # Install requirements
    print("Installing/updating dependencies...")
    pip_cmd = [str(venv_python), "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")]
    try:
        subprocess.run(pip_cmd, check=True)
        print("Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError:
        print("Error installing dependencies.")
        return False


def run_app(debug=False, port=8501):
    """Run the Streamlit app."""
    venv_dir = PROJECT_ROOT / "venv"
    venv_python = venv_dir / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
    
    # Command to run Streamlit app
    streamlit_cmd = [
        str(venv_python), 
        "-m", "streamlit", "run", 
        str(PROJECT_ROOT / "src" / "ui" / "app.py"),
        "--server.port", str(port)
    ]
    
    if debug:
        streamlit_cmd.extend(["--logger.level", "debug"])
    
    print(f"Starting Streamlit server on port {port}...")
    subprocess.run(streamlit_cmd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run AI News Scraper application")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=8501, help="Port to run Streamlit on")
    args = parser.parse_args()
    
    # Change to project root directory
    os.chdir(PROJECT_ROOT)
    
    print("Starting AI News Scraper Web Application...")
    print_version_info()
    
    if not check_python():
        sys.exit(1)
    
    if not setup_virtualenv():
        sys.exit(1)
    
    run_app(debug=args.debug, port=args.port)


if __name__ == "__main__":
    main()
