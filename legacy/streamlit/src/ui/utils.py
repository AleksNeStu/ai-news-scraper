"""
Utility functions for the UI components.
"""

import subprocess
import streamlit as st
from typing import Dict, Optional


def get_git_info() -> Dict[str, str]:
    """
    Get git repository information.
    
    Returns:
        Dictionary containing commit hash, date, subject, branch, and repo URL
    """
    git_info = {
        "commit_hash": "Unknown",
        "commit_date": "Unknown",
        "commit_subject": "Unknown",
        "branch": "Unknown",
        "repo_url": "Unknown",
        "available": False
    }
    
    try:
        # Check if in a git repository
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], stderr=subprocess.DEVNULL)
        
        # Get commit hash
        git_info["commit_hash"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            text=True
        ).strip()
        
        # Get commit date
        git_info["commit_date"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M:%S"], 
            text=True
        ).strip()
        
        # Get commit subject
        git_info["commit_subject"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], 
            text=True
        ).strip()
        
        # Get current branch
        git_info["branch"] = subprocess.check_output(
            ["git", "branch", "--show-current"], 
            text=True
        ).strip()
        
        # Try to get repository URL
        try:
            remote_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            # Format the URL for display (remove .git, convert SSH to HTTPS if needed)
            if remote_url.endswith('.git'):
                remote_url = remote_url[:-4]
            
            # Convert SSH URL to HTTPS format if needed
            if remote_url.startswith('git@'):
                # Example: git@github.com:username/repo.git -> https://github.com/username/repo
                parts = remote_url.split(':')
                if len(parts) == 2:
                    domain = parts[0].split('@')[1]
                    path = parts[1]
                    remote_url = f"https://{domain}/{path}"
            
            git_info["repo_url"] = remote_url
        except (subprocess.SubprocessError, FileNotFoundError):
            git_info["repo_url"] = "Unknown"
        
        git_info["available"] = True
    except (subprocess.SubprocessError, FileNotFoundError):
        # Git not available or not in a git repository
        pass
        
    return git_info


def render_version_info(in_sidebar=True):
    """
    Render version information in the sidebar or as an expander.
    
    Args:
        in_sidebar: Whether the version info is being displayed in the sidebar
    """
    git_info = get_git_info()
    
    if in_sidebar:
        # Render version info directly in the sidebar
        st.sidebar.markdown("### 📋 Version Information")
        if git_info["available"]:
            # Add repository URL with clickable link if available
            repo_url = git_info["repo_url"]
            repo_link = f"[View Repository]({repo_url})" if repo_url != "Unknown" else "Repository URL not available"
            
            # Add commit link if repository URL is available
            commit_link = ""
            if repo_url != "Unknown" and repo_url.startswith("https://github.com"):
                commit_url = f"{repo_url}/commit/{git_info['commit_hash']}"
                commit_link = f" ([view]({commit_url}))"
            
            st.sidebar.markdown(f"""
            **🔖 Commit:** `{git_info["commit_hash"]}`{commit_link}  
            **📅 Date:** {git_info["commit_date"]}  
            **📌 Branch:** `{git_info["branch"]}`  
            **🔍 Message:** {git_info["commit_subject"]}  
            **🌐 Repository:** {repo_link}
            """)
        else:
            st.sidebar.info("Git information not available")
    else:
        # Render version info as an expander in the main content
        if git_info["available"]:
            with st.expander("📋 Version Information"):
                # Add repository URL with clickable link if available
                repo_url = git_info["repo_url"]
                repo_link = f"[View Repository]({repo_url})" if repo_url != "Unknown" else "Repository URL not available"
                
                # Add commit link if repository URL is available
                commit_link = ""
                if repo_url != "Unknown" and repo_url.startswith("https://github.com"):
                    commit_url = f"{repo_url}/commit/{git_info['commit_hash']}"
                    commit_link = f" ([view]({commit_url}))"
                
                st.markdown(f"""
                **🔖 Commit:** `{git_info["commit_hash"]}`{commit_link}  
                **📅 Date:** {git_info["commit_date"]}  
                **📌 Branch:** `{git_info["branch"]}`  
                **🔍 Message:** {git_info["commit_subject"]}  
                **🌐 Repository:** {repo_link}
                """)
        else:
            with st.expander("📋 Version Information"):
                st.info("Git information not available")
