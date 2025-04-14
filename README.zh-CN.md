# 任务管理 MCP 服务

[English](README.md) | [中文](README.zh-CN.md)

基于模型上下文协议(MCP)的智能任务管理服务，帮助自动化项目任务拆解、依赖管理和执行推荐。

## 项目特点

* **自动任务拆解**：从PRD文档自动提取和规划任务结构
* **依赖关系管理**：智能处理任务间的依赖，避免循环依赖
* **智能任务推荐**：根据依赖状态和优先级推荐下一个执行任务
* **子任务展开**：使用LLM自动将主任务展开为详细子任务
* **代码关联**：记录任务与实现代码的关联，提高可追溯性
* **任务优先级**：支持多级任务优先级和标签管理
* **MCP集成**：原生支持模型上下文协议(MCP)，便于与大模型协作

## 快速开始

### 安装

推荐使用uv进行安装：

```bash
# 安装uv
pip install uv

# 安装依赖
uv pip install -r requirements.txt
```

或者使用传统pip安装：

```bash
pip install fastmcp uvicorn pydantic google-generativeai
```

### 环境配置

设置必要的环境变量：

```bash
# Gemini配置
export GEMINI_API_KEY="your-api-key-here"
export LLM_PROVIDER="gemini"
export MODEL_NAME="gemini-1.5-flash"

# 或OpenAI配置
# export OPENAI_API_KEY="your-api-key-here"
# export LLM_PROVIDER="openai"
# export MODEL_NAME="gpt-4o"

# 可选：代理设置
export HTTP_PROXY="http://your-proxy:port"
export HTTPS_PROXY="http://your-proxy:port"

# 可选：输出目录
export MCP_OUTPUT_DIR="/path/to/output"
```

### 基本用法

1. 启动服务 (使用 uv):

```bash
uv run --with fastmcp fastmcp run src/server.py
```

或者直接使用 Python:

```bash
cd src
python server.py 
```

2. 在Cursor IDE中配置MCP服务:

编辑 `~/.cursor/mcp.json` 文件 (通常位于 `C:\Users\<用户名>\.cursor\mcp.json`)，找到 `mcpServers` 部分并添加或更新 `task-manager` 配置:

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
        "D:\\code\\git_project\\task-manager-mcp\\src\\server.py" // 注意: 这里需要替换为你本地 server.py 的绝对路径
      ],
      "env": {
        "GEMINI_API_KEY": "<你的Gemini API Key>",
        "HTTP_PROXY": "http://127.0.0.1:7890", // 如果需要代理
        "HTTPS_PROXY": "http://127.0.0.1:7890", // 如果需要代理
        "MODEL_NAME": "gemini-1.5-flash", // 或其他支持的模型
        "LLM_PROVIDER": "gemini", // 或 openai
        "MCP_OUTPUT_DIR": "D:\\path\\to\\your\\output\\directory\\" // 可选：指定输出目录
      }
    }
    // 可能还有其他服务器配置...
  }
}
```

**注意:**
- 将 `D:\code\git_project\task-manager-mcp\src\server.py` 替换为你本地 `server.py` 文件的**绝对路径**。
- 确保 `env` 中的环境变量设置正确，特别是 API 密钥和代理设置（如果需要）。
- `MCP_OUTPUT_DIR` 是可选的，用于指定任务相关文件（如JSON、Markdown）的输出位置。

3. 在Cursor中使用服务:

```
@task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
```

## 文档

详细文档请参阅 `docs/` 目录:

* [设计文档](docs/design.md) - 系统设计概览
* [快速入门](docs/getting-started.md) - 入门指南
* [API参考](docs/api-reference.md) - API详细说明
* [MCP调用规则](docs/mcp-rules.md) - 大模型调用规范
* [配置示例](docs/config-example.md) - 配置文件示例
* [实现指南](docs/implementation-guide.md) - 开发实现指南
* [安装指南](docs/installation.md) - 详细安装说明
* [待办事项](docs/todolist.md) - 开发计划清单

## 主要功能

### PRD解析与任务拆解

自动从项目需求文档中提取任务和依赖关系:

```
@task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
```

### 任务管理

创建、更新任务（包括状态、依赖关系、代码引用等）:

```
@task-manager add_task name="实现登录功能" description="实现用户登录功能，包括表单验证" priority="high" tags="前端,用户功能"

@task-manager update_task task_id="1" status="in_progress" dependencies="2,3"

@task-manager get_task task_id="1"

@task-manager get_task_list status="todo" priority="high" tag="前端"
```

### 子任务展开

将主任务展开为多个子任务:

```
@task-manager expand_task task_id="1" num_subtasks="5"
```

### 智能任务推荐

获取下一个应该执行的任务:

```
@task-manager get_next_executable_task
```

### 代码引用管理

更新任务关联的代码文件:

```
@task-manager update_task_code_references task_id="1" code_files="src/login.js,src/utils/validation.js"
```

## 系统架构

系统基于Python和FastMCP框架构建，使用MCP工具提供接口。架构包括:

* **MCP服务层**: 处理MCP协议通信和工具调用
* **核心逻辑层**: 实现任务管理、依赖检查等核心功能
* **LLM集成层**: 与Gemini/OpenAI等LLM服务集成，提供智能解析
* **存储层**: 支持内存存储(默认)和数据库存储(可扩展)

## 贡献

欢迎贡献代码、报告问题或提出新功能建议。请参阅[贡献指南](docs/contributing.md)了解详情。

## 许可

MIT License 