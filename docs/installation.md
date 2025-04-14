# 任务管理MCP服务安装指南

本文档提供了任务管理MCP服务的详细安装步骤，包括不同环境和部署方式的说明。

## 1. 系统要求

### 最低要求
- Python 3.10+
- 内存: 512MB+
- 磁盘空间: 100MB+

### 推荐配置
- Python 3.11+
- 内存: 1GB+
- 磁盘空间: 500MB+
- 处理器: 双核或更高

## 2. 基础安装

### 2.1 准备Python环境

确保你拥有Python 3.10或更高版本：

```bash
python --version
```

如果需要安装或升级Python，请访问[Python官方网站](https://www.python.org/downloads/)。

### 2.2 获取代码

从代码仓库克隆项目：

```bash
git clone https://github.com/yourusername/task-manager-mcp.git
cd task-manager-mcp
```

或者下载源码压缩包并解压。

### 2.3 安装依赖

推荐使用uv进行安装（更快且支持子解释器隔离）：

```bash
# 安装uv
pip install uv

# 使用uv安装依赖
uv pip install -r requirements.txt
```

或者使用传统pip安装：

```bash
pip install -r requirements.txt
```

`requirements.txt`文件内容示例：

```
fastmcp>=0.6.0
uvicorn>=0.15.0
pydantic>=1.8.2
google-generativeai>=0.3.0
```

### 2.4 配置LLM

服务可以使用Gemini或OpenAI作为LLM提供商进行PRD解析和任务扩展。配置以下环境变量：

```bash
# Gemini配置
export GEMINI_API_KEY="your-api-key-here"
export LLM_PROVIDER="gemini"
export MODEL_NAME="gemini-1.5-flash"  # 或其它Gemini模型

# 或OpenAI配置
# export OPENAI_API_KEY="your-api-key-here"
# export LLM_PROVIDER="openai"
# export MODEL_NAME="gpt-4o"
```

如果您所在的区域需要使用代理访问这些服务，还可以配置：

```bash
export HTTP_PROXY="http://your-proxy:port"
export HTTPS_PROXY="http://your-proxy:port"
```

### 2.5 配置输出目录

配置任务文件的输出目录：

```bash
export MCP_OUTPUT_DIR="/path/to/output/dir"
```

如果不设置，将默认使用项目根目录下的`output`文件夹。

## 3. 不同环境的安装

### 3.1 开发环境

推荐使用虚拟环境：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
uv pip install -r requirements-dev.txt
```

### 3.2 生产环境

为生产环境进行额外设置：

```bash
# 安装生产依赖
uv pip install -r requirements-prod.txt

# 创建日志目录
mkdir -p /var/log/task-manager-mcp
```

## 4. 在Cursor IDE中配置

### 4.1 配置MCP服务

编辑Cursor的MCP配置文件：

* Windows: `C:\Users\<用户名>\.cursor\mcp.json`
* macOS: `~/.cursor/mcp.json`
* Linux: `~/.cursor/mcp.json`

添加以下配置：

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
        "D:\\path\\to\\task-manager-mcp\\src\\server.py"
      ],
      "env": {
        "GEMINI_API_KEY": "<你的Gemini API Key>",
        "HTTP_PROXY": "http://127.0.0.1:7890",
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "MODEL_NAME": "gemini-1.5-flash",
        "LLM_PROVIDER": "gemini",
        "MCP_OUTPUT_DIR": "D:\\path\\to\\output\\dir\\"
      }
    }
  }
}
```

请确保：
- 替换`D:\\path\\to\\task-manager-mcp\\src\\server.py`为服务器脚本文件的**绝对路径**
- 替换`<你的Gemini API Key>`为你的实际API密钥
- 根据需要配置代理设置
- 替换`D:\\path\\to\\output\\dir\\`为你希望存储任务文件的目录

### 4.2 重启Cursor IDE

配置完成后，重启Cursor IDE以应用更改。

## 5. Docker安装

### 5.1 Dockerfile

创建Dockerfile：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装UV
RUN pip install uv

# 拷贝项目文件
COPY requirements.txt .
COPY src/ src/
COPY docs/ docs/

# 创建输出目录
RUN mkdir -p /app/output/tasks /app/output/md /app/output/logs

# 设置环境变量
ENV PYTHONPATH=/app
ENV MCP_OUTPUT_DIR=/app/output

# 暴露端口
EXPOSE 8000

# 使用UV运行服务
CMD ["uv", "run", "--with", "fastmcp", "fastmcp", "run", "/app/src/server.py"]
```

### 5.2 构建与运行

```bash
# 构建镜像
docker build -t task-manager-mcp .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your-api-key \
  -e MODEL_NAME=gemini-1.5-flash \
  -e LLM_PROVIDER=gemini \
  --name task-manager-mcp \
  task-manager-mcp
```

## 6. 验证安装

启动服务：

```bash
# 使用UV运行(推荐)
uv run --with fastmcp fastmcp run src/server.py

# 或直接使用Python运行
cd src
python server.py
```

测试服务是否正常运行：

```bash
# 使用curl请求
curl http://localhost:8000/health

# 预期输出
{"status":"ok","version":"1.0.0"}
```

## 7. 环境变量一览

所有支持的环境变量：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `GEMINI_API_KEY` | Gemini API密钥 | - |
| `OPENAI_API_KEY` | OpenAI API密钥 | - |
| `LLM_PROVIDER` | LLM提供商，`gemini`或`openai` | `gemini` |
| `MODEL_NAME` | 使用的LLM模型名称 | `gemini-1.5-flash` |
| `HTTP_PROXY` | HTTP代理 | - |
| `HTTPS_PROXY` | HTTPS代理 | - |
| `MCP_OUTPUT_DIR` | 输出文件保存路径 | `项目根目录/output` |
| `MCP_LOGS_DIR` | 日志文件路径 | `MCP_OUTPUT_DIR/logs` |
| `MCP_TASKS_DIR` | 任务JSON文件路径 | `MCP_OUTPUT_DIR/tasks` |
| `MCP_MD_DIR` | Markdown文件路径 | `MCP_OUTPUT_DIR/md` |
| `MCP_SERVICE_PORT` | 服务端口 | `8000` |

## 8. 常见问题

### 8.1 依赖安装失败

问题：安装依赖时出现错误

解决：确保Python版本兼容，并尝试：

```bash
uv pip install -r requirements.txt --no-cache
```

### 8.2 LLM相关错误

问题：PRD解析或任务展开失败，出现LLM相关错误

解决：
1. 确认LLM API密钥设置正确
2. 检查网络连接或代理设置
3. 确保使用的模型名称正确
4. 如有代理需求，确保设置了`HTTP_PROXY`和`HTTPS_PROXY`环境变量

### 8.3 Cursor无法连接

问题：Cursor IDE无法连接到MCP服务

解决：
1. 确认服务正在运行
2. 检查配置中的路径是否正确（Windows路径需使用双反斜杠）
3. 确保填写的是绝对路径而非相对路径
4. 检查环境变量设置是否正确

## 9. 更新

更新到最新版本：

```bash
# 更新代码库
git pull

# 更新依赖
pip install -r requirements.txt --upgrade
``` 