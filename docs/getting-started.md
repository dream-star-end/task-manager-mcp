# 任务管理MCP服务快速入门指南

## 环境准备

### 系统要求
- Python 3.10+
- pip 22.0+

### 安装依赖

推荐使用uv进行安装（更快且支持子解释器隔离）：

```bash
# 安装uv
pip install uv

# 安装依赖
uv pip install -r requirements.txt
```

或者使用传统pip安装：

```bash
# 安装依赖
pip install fastmcp uvicorn pydantic google-generativeai
```

### 配置LLM

服务可以使用Gemini或OpenAI作为LLM提供商，配置以下环境变量：

```bash
# Gemini配置(推荐)
export GEMINI_API_KEY="your-api-key-here"
export LLM_PROVIDER="gemini"
export MODEL_NAME="gemini-1.5-flash"  # 或其它Gemini模型

# 或者OpenAI配置
# export OPENAI_API_KEY="your-api-key-here"
# export LLM_PROVIDER="openai" 
# export MODEL_NAME="gpt-4o"
```

如果您所在的区域需要使用代理访问这些服务，还可以配置：

```bash
export HTTP_PROXY="http://your-proxy:port"
export HTTPS_PROXY="http://your-proxy:port"
```

### 配置输出目录

配置任务文件的输出目录：

```bash
export MCP_OUTPUT_DIR="/path/to/output/dir"
```

如果不设置，将默认使用项目根目录下的`output`文件夹。

## 服务启动

### 使用uv启动(推荐)
```bash
# 使用uv启动服务
uv run --with fastmcp fastmcp run src/server.py
```

### 使用Python启动
```bash
# 进入src目录
cd src

# 直接使用Python启动
python server.py
```

### 在IDE中配置MCP服务

1. 在Cursor中，找到并打开`~/.cursor/mcp.json`文件（Windows路径通常为`C:\Users\<用户名>\.cursor\mcp.json`）
2. 在`mcp.json`文件中，找到 `mcpServers` 部分，添加或更新 `task-manager` 配置:

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
        "D:\\code\\git_project\\task-manager-mcp\\src\\server.py"
      ],
      "env": {
        "GEMINI_API_KEY": "<你的Gemini API Key>",
        "HTTP_PROXY": "http://127.0.0.1:7890",
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "MODEL_NAME": "gemini-1.5-flash",
        "LLM_PROVIDER": "gemini",
        "MCP_OUTPUT_DIR": "D:\\path\\to\\your\\output\\dir\\"
      }
    }
  }
}
```

替换以下内容:
- `D:\\code\\git_project\\task-manager-mcp\\src\\server.py`: 替换为你本地 `server.py` 文件的**绝对路径**。
- `<你的Gemini API Key>`: 替换为你的实际 API 密钥。
- 根据需要配置代理、模型名称和 LLM 提供商。
- `MCP_OUTPUT_DIR` 是可选的，用于指定任务相关文件（如JSON、Markdown）的输出位置。

## 使用方法

### 在Cursor中使用服务
1. 重启Cursor IDE以应用新配置
2. 使用快捷键 `Ctrl+I` 打开MCP输入框
3. 输入 `@task-manager` 以访问任务管理工具
4. 使用相应的工具，例如：
   ```
   @task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
   ```

### API调用示例

1. 解析PRD文档：
```
@task-manager decompose_prd prd_content="file:///D:/path/to/prd.md"
```

**注意**：使用`file://`格式时，**必须**传入绝对路径，例如：
- Windows: `file:///C:/Users/username/documents/prd.md` 或 `file:///D:/projects/prd.md`
- Linux/macOS: `file:///home/username/documents/prd.md` 或 `file:///opt/projects/prd.md`

相对路径将无法正确读取文件。

2. 获取下一个可执行任务：
```
@task-manager get_next_executable_task
```

3. 创建新任务：
```
@task-manager add_task name="实现登录功能" description="实现用户登录功能，包括表单验证" priority="high" tags="前端,用户功能"
```

4. 更新任务为进行中状态：
```
@task-manager update_task task_id="1" status="in_progress"
```

5. 为任务添加代码引用：
```
@task-manager update_task_code_references task_id="1" code_files="src/main.py,src/utils.py"
```

6. 将任务展开为子任务：
```
@task-manager expand_task task_id="1" num_subtasks="5"
```

7. 获取任务列表：
```
@task-manager get_task_list status="todo" priority="high" tag="前端"
```

8. 获取特定任务详情：
```
@task-manager get_task task_id="1"
```

## 常见问题

### LLM相关错误

问题：PRD解析或任务展开失败，出现LLM相关错误

解决：
1. 确认LLM API密钥设置正确
2. 检查网络连接或代理设置
3. 确保使用的模型名称正确
4. 如有代理需求，确保设置了`HTTP_PROXY`和`HTTPS_PROXY`环境变量

### 连接超时
- 确认服务是否正常运行
- 检查防火墙设置
- 验证端口是否被占用

### 调用失败
- 确认参数格式是否正确
- 检查任务ID是否存在
- 查看服务日志了解详细错误信息

## 调试技巧

### 查看完整日志
通过设置环境变量控制日志级别：
```bash
export MCP_LOG_LEVEL=DEBUG
```

### 验证服务健康状态
```bash
curl http://localhost:8000/health
```

### 手动测试API
可以使用curl或Postman工具手动测试API端点：

```bash
curl -X POST http://localhost:8000/mcp/tools/get_next_executable_task -H "Content-Type: application/json" -d '{}'
``` 