# 任务管理 MCP 服务

基于模型上下文协议(MCP)的智能任务管理服务，帮助自动化项目任务拆解、依赖管理和执行推荐。

## 项目特点

* **自动任务拆解**：从PRD文档自动提取和规划任务结构
* **依赖关系管理**：智能处理任务间的依赖，避免循环依赖
* **智能任务推荐**：根据依赖状态和优先级推荐下一个执行任务
* **代码关联**：记录任务与实现代码的关联，提高可追溯性
* **MCP集成**：原生支持模型上下文协议(MCP)，便于与大模型协作

## 快速开始

### 安装

```bash
# 安装MCP SDK和依赖
pip install mcp-python-sdk uvicorn pydantic
```

### 基本用法

1. 启动服务:

```bash
python -m mcp run server.py
```

2. 在Cursor IDE中配置MCP服务:

编辑 `~/.cursor/mcp.json` 文件添加:

```json
"task-manager": {
  "command": "python",
  "args": [
    "-m",
    "mcp",
    "run",
    "/path/to/server.py"
  ],
  "env": {
    "DEEPSEEK_API_KEY": "sk-e4ab454f0fc24c7fb7cfdc7af42e23fa"
  }
}
```

3. 在Cursor中使用服务:

```
@task-manager 解析这个PRD文档：file://path/to/prd.md
```

## 文档

详细文档请参阅 `docs/` 目录:

* [设计文档](docs/design.md) - 系统设计概览
* [快速入门](docs/getting-started.md) - 入门指南
* [API参考](docs/api-reference.md) - API详细说明
* [MCP调用规则](docs/mcp-rules.md) - 大模型调用规范
* [配置示例](docs/config-example.md) - 配置文件示例
* [实现指南](docs/implementation-guide.md) - 开发实现指南
* [待办事项](docs/todolist.md) - 开发计划清单

## 主要功能

### PRD解析与任务拆解

自动从项目需求文档中提取任务和依赖关系:

```
<mcp:tool name="decompose_prd">
<mcp:parameter name="prd_content">file://path/to/prd.md</mcp:parameter>
</mcp:tool>
```

### 任务管理

创建、更新任务和管理依赖关系:

```
<mcp:tool name="add_task">
<mcp:parameter name="name">实现登录功能</mcp:parameter>
<mcp:parameter name="description">开发用户登录界面和认证逻辑</mcp:parameter>
</mcp:tool>
```

### 智能任务推荐

获取下一个应该执行的任务:

```
<mcp:tool name="get_next_executable_task">
</mcp:tool>
```

## 系统架构

系统基于Python和FastMCP框架构建，使用MCP工具提供接口。架构包括:

* **MCP服务层**: 处理MCP协议通信和工具调用
* **核心逻辑层**: 实现任务管理、依赖检查等核心功能
* **存储层**: 支持内存存储(默认)和数据库存储(可扩展)

## 贡献

欢迎贡献代码、报告问题或提出新功能建议。

## 许可

MIT License