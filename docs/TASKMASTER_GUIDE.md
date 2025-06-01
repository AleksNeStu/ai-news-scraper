# TaskMaster AI - Complete Integration Guide

**Single Source of Truth for TaskMaster across all IDEs and development environments**

## Overview

TaskMaster AI is a comprehensive task management system that integrates with development environments through the Model Context Protocol (MCP). This guide provides the complete reference for using TaskMaster with Claude, VS Code, Cursor, and other MCP-compatible tools.

## Quick Start

### 1. Installation & Setup
```bash
# Install TaskMaster CLI globally
npm install -g task-master-ai

# Initialize project
task-master init

# Verify installation
task-master --version
```

### 2. MCP Configuration

#### For VS Code (.vscode/mcp.json)
```json
{
    "mcpServers": {
        "task-master-ai": {
            "command": "npx",
            "args": ["-y", "--package=task-master-ai", "task-master-ai"],
            "env": {
                "ANTHROPIC_API_KEY": "your_key_here",
                "OPENAI_API_KEY": "your_key_here",
                "PERPLEXITY_API_KEY": "your_key_here"
            }
        }
    }
}
```

#### For Cursor (.cursor/mcp.json)
```json
{
    "mcpServers": {
        "task-master-ai": {
            "command": "npx",
            "args": ["-y", "--package=task-master-ai", "task-master-ai"],
            "env": {
                "ANTHROPIC_API_KEY": "your_key_here",
                "OPENAI_API_KEY": "your_key_here",
                "PERPLEXITY_API_KEY": "your_key_here"
            }
        }
    }
}
```

## Core MCP Tools Reference

### Project Management

#### `mcp_taskmaster-ai2_initialize_project`
**Purpose**: Initialize new TaskMaster project structure
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "yes": true,
    "skipInstall": false,
    "addAliases": false
}
```

#### `mcp_taskmaster-ai2_parse_prd`
**Purpose**: Generate tasks from Product Requirements Document
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "input": ".taskmaster/docs/prd.txt",
    "numTasks": "10",
    "research": true,
    "force": false
}
```

### Task Operations

#### `mcp_taskmaster-ai2_get_tasks`
**Purpose**: List all tasks with optional filtering
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "status": "pending", // optional: pending, done, in-progress, review
    "withSubtasks": true,
    "file": "tasks/tasks.json" // optional custom path
}
```

#### `mcp_taskmaster-ai2_get_task`
**Purpose**: Get detailed information about specific task
```javascript
{
    "id": "5",
    "projectRoot": "/absolute/path/to/project",
    "status": "pending" // optional filter for subtasks
}
```

#### `mcp_taskmaster-ai2_next_task`
**Purpose**: Find the next task to work on based on dependencies
```javascript
{
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_add_task`
**Purpose**: Add new task using AI generation
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "prompt": "Implement user authentication system",
    "priority": "high", // high, medium, low
    "research": true,
    "dependencies": "1,3,5" // comma-separated task IDs
}
```

#### `mcp_taskmaster-ai2_update_task`
**Purpose**: Update single task with new information
```javascript
{
    "id": "5",
    "projectRoot": "/absolute/path/to/project",
    "prompt": "Updated requirements: add OAuth support",
    "research": false
}
```

#### `mcp_taskmaster-ai2_set_task_status`
**Purpose**: Update task or subtask status
```javascript
{
    "id": "5", // or "5.2" for subtask
    "status": "done", // pending, done, in-progress, review, deferred, cancelled
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_remove_task`
**Purpose**: Remove task permanently
```javascript
{
    "id": "5", // or "5.2" for subtask
    "projectRoot": "/absolute/path/to/project",
    "confirm": true
}
```

### Subtask Management

#### `mcp_taskmaster-ai2_expand_task`
**Purpose**: Break down task into detailed subtasks
```javascript
{
    "id": "5",
    "projectRoot": "/absolute/path/to/project",
    "num": "4", // number of subtasks to generate
    "force": true, // overwrite existing subtasks
    "research": true,
    "prompt": "Focus on security and performance"
}
```

#### `mcp_taskmaster-ai2_add_subtask`
**Purpose**: Add subtask to existing task
```javascript
{
    "id": "5", // parent task ID
    "projectRoot": "/absolute/path/to/project",
    "title": "Implement password validation",
    "description": "Add client-side and server-side validation",
    "status": "pending"
}
```

#### `mcp_taskmaster-ai2_update_subtask`
**Purpose**: Append information to subtask
```javascript
{
    "id": "5.2", // subtaskId in format parentId.subtaskId
    "projectRoot": "/absolute/path/to/project",
    "prompt": "Added implementation notes: use bcrypt for hashing"
}
```

#### `mcp_taskmaster-ai2_remove_subtask`
**Purpose**: Remove subtask from parent
```javascript
{
    "id": "5.2", // subtaskId in format parentId.subtaskId
    "projectRoot": "/absolute/path/to/project",
    "convert": false // true to convert to standalone task
}
```

#### `mcp_taskmaster-ai2_clear_subtasks`
**Purpose**: Remove all subtasks from specified tasks
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "id": "5,6,7", // comma-separated task IDs
    "all": false // true to clear from all tasks
}
```

### Dependencies & Structure

#### `mcp_taskmaster-ai2_add_dependency`
**Purpose**: Add dependency relationship between tasks
```javascript
{
    "id": "5", // task that depends on another
    "dependsOn": "3", // task that must be completed first
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_remove_dependency`
**Purpose**: Remove dependency relationship
```javascript
{
    "id": "5",
    "dependsOn": "3",
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_validate_dependencies`
**Purpose**: Check for dependency issues (circular references, etc.)
```javascript
{
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_fix_dependencies`
**Purpose**: Automatically fix invalid dependencies
```javascript
{
    "projectRoot": "/absolute/path/to/project"
}
```

#### `mcp_taskmaster-ai2_move_task`
**Purpose**: Reorganize task hierarchy and ordering
```javascript
{
    "from": "5", // task to move
    "to": "7", // destination position
    "projectRoot": "/absolute/path/to/project"
}
```

### Analysis & Optimization

#### `mcp_taskmaster-ai2_analyze_project_complexity`
**Purpose**: Analyze task complexity and generate recommendations
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "threshold": 5, // complexity score threshold (1-10)
    "research": true,
    "from": 1, // optional: analyze range of tasks
    "to": 10,
    "ids": "1,3,5,7" // optional: specific task IDs
}
```

#### `mcp_taskmaster-ai2_complexity_report`
**Purpose**: Display complexity analysis in readable format
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "file": ".taskmaster/reports/task-complexity-report.json"
}
```

#### `mcp_taskmaster-ai2_expand_all`
**Purpose**: Expand all pending tasks into subtasks
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "force": false, // regenerate existing subtasks
    "research": true,
    "num": "auto", // or specific number like "4"
    "prompt": "Focus on modular architecture"
}
```

### Bulk Operations

#### `mcp_taskmaster-ai2_update`
**Purpose**: Update multiple upcoming tasks with new context
```javascript
{
    "from": "5", // update tasks starting from this ID
    "prompt": "New requirement: must support mobile devices",
    "projectRoot": "/absolute/path/to/project",
    "research": true
}
```

### Configuration & Models

#### `mcp_taskmaster-ai2_models`
**Purpose**: Configure AI models for different operations
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "setMain": "claude-3-5-sonnet-20241022", // primary model
    "setResearch": "gpt-4-turbo", // research model
    "setFallback": "gpt-3.5-turbo", // fallback model
    "listAvailableModels": true
}
```

### File Generation

#### `mcp_taskmaster-ai2_generate`
**Purpose**: Generate individual task files in tasks/ directory
```javascript
{
    "projectRoot": "/absolute/path/to/project",
    "file": ".taskmaster/tasks/tasks.json",
    "output": ".taskmaster/tasks/" // optional custom output directory
}
```

## CLI Commands (Fallback/Direct Use)

| MCP Tool | CLI Command | Description |
|----------|-------------|-------------|
| `initialize_project` | `task-master init` | Initialize project structure |
| `parse_prd` | `task-master parse-prd --input=prd.txt` | Generate tasks from PRD |
| `get_tasks` | `task-master list` | List all tasks |
| `get_task` | `task-master show <id>` | Show specific task |
| `next_task` | `task-master next` | Find next task to work on |
| `add_task` | `task-master add-task --prompt="..."` | Add new task |
| `set_task_status` | `task-master set-status --id=<id> --status=done` | Update task status |
| `expand_task` | `task-master expand --id=<id> --force --research` | Break down task |
| `analyze_project_complexity` | `task-master analyze-complexity --research` | Analyze complexity |
| `generate` | `task-master generate` | Generate task files |

## Development Workflow

### 1. Project Initialization
```javascript
// Initialize TaskMaster in new project
mcp_taskmaster-ai2_initialize_project({
    "projectRoot": "/path/to/project",
    "yes": true
})

// Parse PRD to generate initial tasks
mcp_taskmaster-ai2_parse_prd({
    "projectRoot": "/path/to/project",
    "input": ".taskmaster/docs/prd.txt",
    "numTasks": "15",
    "research": true
})
```

### 2. Daily Development Cycle
```javascript
// Start session: Get task overview
mcp_taskmaster-ai2_get_tasks({
    "projectRoot": "/path/to/project",
    "withSubtasks": true
})

// Find next task to work on
mcp_taskmaster-ai2_next_task({
    "projectRoot": "/path/to/project"
})

// Get detailed task information
mcp_taskmaster-ai2_get_task({
    "id": "5",
    "projectRoot": "/path/to/project"
})

// Expand complex tasks into subtasks
mcp_taskmaster-ai2_expand_task({
    "id": "5",
    "projectRoot": "/path/to/project",
    "force": true,
    "research": true
})
```

### 3. Task Completion
```javascript
// Update subtask with progress notes
mcp_taskmaster-ai2_update_subtask({
    "id": "5.2",
    "projectRoot": "/path/to/project",
    "prompt": "Implemented user validation with proper error handling"
})

// Mark subtask as complete
mcp_taskmaster-ai2_set_task_status({
    "id": "5.2",
    "status": "done",
    "projectRoot": "/path/to/project"
})

// Mark parent task as complete when all subtasks done
mcp_taskmaster-ai2_set_task_status({
    "id": "5",
    "status": "done",
    "projectRoot": "/path/to/project"
})
```

### 4. Project Evolution
```javascript
// Add new tasks discovered during development
mcp_taskmaster-ai2_add_task({
    "projectRoot": "/path/to/project",
    "prompt": "Add API rate limiting to prevent abuse",
    "priority": "high",
    "research": true
})

// Update upcoming tasks with new context
mcp_taskmaster-ai2_update({
    "from": "10",
    "prompt": "New requirement: must integrate with external payment system",
    "projectRoot": "/path/to/project",
    "research": true
})
```

## Best Practices

### 1. Task Management
- Use `next_task` to maintain logical development flow
- Break down complex tasks (complexity > 5) with `expand_task`
- Keep subtasks focused and actionable (< 2 hours of work)
- Update task status regularly to track progress

### 2. Dependencies
- Validate dependencies regularly with `validate_dependencies`
- Use `add_dependency` to enforce proper task order
- Fix circular dependencies with `fix_dependencies`

### 3. Project Analysis
- Run `analyze_project_complexity` before major development phases
- Use research mode for better task generation and analysis
- Review complexity reports to identify bottlenecks

### 4. Model Configuration
- Set appropriate models for different operations
- Use research-capable models for complex analysis
- Configure fallback models for reliability

## File Structure

```
project-root/
├── .taskmaster/
│   ├── config.json          # TaskMaster configuration
│   ├── docs/
│   │   └── prd.txt          # Project requirements (TaskMaster format)
│   ├── tasks/
│   │   ├── tasks.json       # Main tasks configuration
│   │   ├── task-1.md        # Individual task files (auto-generated)
│   │   └── task-2.md
│   ├── reports/
│   │   └── task-complexity-report.json
│   └── templates/
├── .vscode/
│   ├── mcp.json            # VS Code MCP configuration
│   └── tasks.json          # VS Code tasks
├── .cursor/
│   └── mcp.json            # Cursor MCP configuration
└── docs/
    ├── PRD.md              # Project requirements (human-readable)
    ├── TASK_MANAGEMENT.md  # Task management framework
    └── TASKMASTER_GUIDE.md # This guide
```

## API Keys Configuration

### Required Environment Variables
```bash
# Primary AI providers
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

# Optional providers
PERPLEXITY_API_KEY=your_perplexity_key
GOOGLE_API_KEY=your_google_key
XAI_API_KEY=your_xai_key
OPENROUTER_API_KEY=your_openrouter_key
MISTRAL_API_KEY=your_mistral_key
AZURE_OPENAI_API_KEY=your_azure_key
OLLAMA_API_KEY=your_ollama_key
```

### MCP Configuration Template
```json
{
    "mcpServers": {
        "task-master-ai": {
            "command": "npx",
            "args": ["-y", "--package=task-master-ai", "task-master-ai"],
            "env": {
                "ANTHROPIC_API_KEY": "sk-ant-api03-...",
                "OPENAI_API_KEY": "sk-...",
                "PERPLEXITY_API_KEY": "pplx-..."
            }
        }
    }
}
```

## Troubleshooting

### Common Issues

1. **"MCP server failed to start"**
   - Verify `task-master-ai` is installed globally: `npm install -g task-master-ai`
   - Check API keys are properly configured in MCP configuration

2. **"Invalid project root"**
   - Ensure `projectRoot` parameter uses absolute paths
   - Initialize project with `initialize_project` if not done

3. **"Task generation failed"**
   - Verify API keys for selected AI model provider
   - Check internet connectivity for AI API access
   - Use fallback models if primary model fails

4. **"Circular dependency detected"**
   - Run `validate_dependencies` to identify issues
   - Use `fix_dependencies` to automatically resolve
   - Manually adjust dependencies if needed

### Debug Commands
```bash
# Check TaskMaster installation
task-master --version

# Validate project structure
task-master validate-dependencies

# Test MCP connection (in IDE with MCP support)
mcp_taskmaster-ai2_get_tasks({"projectRoot": "/path/to/project"})
```

## Version Compatibility

- **TaskMaster AI**: 0.16.0+
- **Node.js**: 16.0.0+
- **MCP Protocol**: 1.0.0+
- **VS Code**: 1.85.0+
- **Cursor**: Latest version

---

**This document serves as the single source of truth for TaskMaster AI integration across all development environments. Keep this file updated as the primary reference.**
