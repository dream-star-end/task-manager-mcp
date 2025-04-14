# Task Manager MCP Service

[English](README.md) | [中文](README.zh-CN.md)

An intelligent task management service based on Model Context Protocol (MCP), helping to automate project task breakdown, dependency management, and execution recommendations.

## Features

* **Automated Task Breakdown**: Automatically extract and plan task structures from PRD documents
* **Dependency Management**: Intelligently handle dependencies between tasks, avoiding circular dependencies
* **Smart Task Recommendations**: Recommend the next task to execute based on dependency status and priority
* **Subtask Expansion**: Use LLM to automatically expand main tasks into detailed subtasks
* **Code Association**: Record associations between tasks and implementation code for better traceability
* **Task Priority**: Support multi-level task priorities and tag management
* **MCP Integration**: Native support for Model Context Protocol (MCP) for easy collaboration with LLMs

## Quick Start

### Installation

Recommended installation using uv:

```bash
# Install uv
pip install uv

# Install dependencies
uv pip install -r requirements.txt
```

Or use traditional pip installation:

```bash
pip install fastmcp uvicorn pydantic google-generativeai
```

### Environment Configuration

Set necessary environment variables:

```bash
# Gemini configuration
export GEMINI_API_KEY="your-api-key-here"
export LLM_PROVIDER="gemini"
export MODEL_NAME="gemini-1.5-flash"

# Or OpenAI configuration
# export OPENAI_API_KEY="your-api-key-here"
# export LLM_PROVIDER="openai"
# export MODEL_NAME="gpt-4o"

# Optional: proxy settings
export HTTP_PROXY="http://your-proxy:port"
export HTTPS_PROXY="http://your-proxy:port"

# Optional: output directory
export MCP_OUTPUT_DIR="/path/to/output"
```

### Basic Usage

1. Start the service (using uv):

```bash
uv run --with fastmcp fastmcp run src/server.py
```

Or directly using Python:

```bash
cd src
python server.py 
```

2. Configure MCP service in Cursor IDE:

Edit the `~/.cursor/mcp.json` file (usually located at `C:\Users\<username>\.cursor\mcp.json`), find the `mcpServers` section and add or update the `task-manager` configuration:

```json
{
  "mcpServers": {
    "task-manager": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "fastmcp",
        "run",
        "D:\\code\\git_project\\task-manager-mcp\\src\\server.py" // Note: Replace this with the absolute path to your local server.py
      ],
      "env": {
        "GEMINI_API_KEY": "<Your Gemini API Key>",
        "HTTP_PROXY": "http://127.0.0.1:7890", // If proxy is needed
        "HTTPS_PROXY": "http://127.0.0.1:7890", // If proxy is needed
        "MODEL_NAME": "gemini-1.5-flash", // Or other supported models
        "LLM_PROVIDER": "gemini", // Or openai
        "MCP_OUTPUT_DIR": "D:\\path\\to\\your\\output\\directory\\" // Optional: specify output directory
      }
    }
    // There might be other server configurations...
  }
}
```

**Note:**
- Replace `D:\code\git_project\task-manager-mcp\src\server.py` with the **absolute path** to your local `server.py` file.
- Ensure the environment variables in `env` are set correctly, especially the API key and proxy settings (if needed).
- `MCP_OUTPUT_DIR` is optional, used to specify the output location for task-related files (such as JSON, Markdown).

3. Using the service in Cursor:

```
@task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
```

## Documentation

For detailed documentation, please refer to the `docs/` directory:

* [Design Document](docs/design.md) - System design overview
* [Getting Started](docs/getting-started.md) - Getting started guide
* [API Reference](docs/api-reference.md) - Detailed API reference
* [MCP Rules](docs/mcp-rules.md) - LLM calling conventions
* [Configuration Examples](docs/config-example.md) - Configuration examples
* [Implementation Guide](docs/implementation-guide.md) - Implementation guide
* [Installation Guide](docs/installation.md) - Detailed installation instructions
* [To-Do List](docs/todolist.md) - Development roadmap

## Key Functions

### PRD Parsing and Task Breakdown

Automatically extract tasks and dependencies from project requirement documents:

```
@task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
```

### Task Management

Create and update tasks (including status, dependencies, code references, etc.):

```
@task-manager add_task name="Implement login function" description="Implement user login function, including form validation" priority="high" tags="frontend,user function"

@task-manager update_task task_id="1" status="in_progress" dependencies="2,3"

@task-manager get_task task_id="1"

@task-manager get_task_list status="todo" priority="high" tag="frontend"
```

### Subtask Expansion

Expand a main task into multiple subtasks:

```
@task-manager expand_task task_id="1" num_subtasks="5"
```

### Smart Task Recommendation

Get the next task that should be executed:

```
@task-manager get_next_executable_task
```

### Code Reference Management

Update code files associated with a task:

```
@task-manager update_task_code_references task_id="1" code_files="src/login.js,src/utils/validation.js"
```

## System Architecture

The system is built on Python and the FastMCP framework, providing interfaces using MCP tools. The architecture includes:

* **MCP Service Layer**: Handles MCP protocol communication and tool invocation
* **Core Logic Layer**: Implements core features such as task management and dependency checking
* **LLM Integration Layer**: Integrates with LLM services like Gemini/OpenAI for intelligent parsing
* **Storage Layer**: Supports in-memory storage (default) and database storage (extensible)

## Contributing

Contributions are welcome, including code contributions, issue reports, or new feature suggestions. Please refer to the [Contributing Guide](docs/contributing.md) for details.

## License

MIT License