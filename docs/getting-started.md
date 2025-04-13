# 任务管理MCP服务快速入门指南

## 环境准备

### 系统要求
- Python 3.10+
- pip 22.0+

### 安装依赖
```bash
# 安装MCP SDK
pip install mcp-python-sdk

# 安装其他依赖
pip install uvicorn
pip install pydantic
```

## 服务启动

### 开发模式启动
```bash
# 使用MCP命令行工具启动服务
python -m mcp run server.py
```

### 生产模式启动
```bash
# 直接使用uvicorn启动
uvicorn server:mcp --host 0.0.0.0 --port 8000
```

### 在IDE中配置MCP服务

1. 在Cursor中，找到并打开`~/.cursor/mcp.json`文件（Windows路径通常为`C:\Users\<用户名>\.cursor\mcp.json`）
2. 在`mcp.json`文件中添加以下配置:

```json
"task-manager": {
  "command": "<Python解释器路径>",
  "args": [
    "-m",
    "mcp",
    "run",
    "<server.py的绝对路径>"
  ],
  "env": {
    "MCP_SERVICE_PORT": "8000",
    "MCP_LOG_LEVEL": "INFO"
  }
}
```

替换以下内容:
- `<Python解释器路径>`: 你的Python解释器路径，比如`C:\\Users\\username\\AppData\\Local\\Programs\\Python\\Python310\\python.exe`
- `<server.py的绝对路径>`: 服务器脚本文件的绝对路径，比如`D:\\code\\task-manager-mcp\\server.py`

## 使用方法

### 连接服务
大模型可以使用以下URL连接到MCP服务：
```
http://localhost:8000/mcp
```

### 在Cursor中使用服务
1. 重启Cursor IDE以应用新配置
2. 使用快捷键 `Ctrl+I` 打开MCP输入框
3. 输入 `@task-manager` 以访问任务管理工具
4. 使用相应的工具，例如：
   ```
   @task-manager 解析PRD文档并创建任务
   ```

### API调用示例

1. 解析PRD文档：
```
<mcp:tool name="decompose_prd">
<mcp:parameter name="prd_content">file://path/to/prd.md</mcp:parameter>
</mcp:tool>
```

2. 获取下一个可执行任务：
```
<mcp:tool name="get_next_executable_task">
<mcp:parameter name="limit">3</mcp:parameter>
</mcp:tool>
```

3. 更新任务为进行中状态：
```
<mcp:tool name="update_task">
<mcp:parameter name="task_id">task-123</mcp:parameter>
<mcp:parameter name="status">in_progress</mcp:parameter>
</mcp:tool>
```

4. 标记任务为已完成：
```
<mcp:tool name="update_task">
<mcp:parameter name="task_id">task-123</mcp:parameter>
<mcp:parameter name="status">done</mcp:parameter>
<mcp:parameter name="actual_hours">3.5</mcp:parameter>
</mcp:tool>
```

5. 为任务添加代码引用：
```
<mcp:tool name="update_task_code_references">
<mcp:parameter name="task_id">task-123</mcp:parameter>
<mcp:parameter name="code_files">src/main.py,src/utils.py</mcp:parameter>
</mcp:tool>
```

## 常见问题

### 连接超时
- 确认服务是否正常运行
- 检查防火墙设置
- 验证端口是否被占用

### 调用失败
- 确认参数格式是否正确
- 检查任务ID是否存在
- 查看服务日志了解详细错误信息

## 调试技巧

### 开启调试模式
```bash
python -m mcp run server.py --debug
```

### 查看完整日志
通过设置环境变量控制日志级别：
```bash
export MCP_LOG_LEVEL=DEBUG
``` 