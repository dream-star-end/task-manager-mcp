# 任务管理MCP服务配置示例

本文档提供任务管理MCP服务的配置示例，包括环境变量配置和部署选项。

## 1. 环境变量配置

系统支持以下环境变量进行配置：

### LLM配置

```bash
# Gemini配置(推荐)
export GEMINI_API_KEY="your-gemini-api-key"     # Gemini API密钥
export LLM_PROVIDER="gemini"                   # 设置使用Gemini作为LLM供应商
export MODEL_NAME="gemini-1.5-flash"            # 使用的模型，可选值：gemini-1.5-flash, gemini-1.5-pro等

# 或OpenAI配置
# export OPENAI_API_KEY="your-openai-api-key"   # OpenAI API密钥
# export LLM_PROVIDER="openai"                  # 设置使用OpenAI作为LLM供应商
# export MODEL_NAME="gpt-4o"                    # 使用的模型，可选值：gpt-4o, gpt-4-turbo等
```

### 代理配置

在某些网络环境下，可能需要配置代理才能访问LLM服务：

```bash
export HTTP_PROXY="http://127.0.0.1:7890"       # HTTP代理
export HTTPS_PROXY="http://127.0.0.1:7890"      # HTTPS代理
```

### 输出目录配置

配置任务相关文件的输出位置：

```bash
# 主输出目录(默认为项目根目录下的output文件夹)
export MCP_OUTPUT_DIR="/path/to/output"

# 以下为可选，如果不设置则使用MCP_OUTPUT_DIR下对应子目录
export MCP_LOGS_DIR="/path/to/logs"             # 日志文件目录
export MCP_TASKS_DIR="/path/to/tasks"           # 任务JSON文件目录
export MCP_MD_DIR="/path/to/md"                 # Markdown文件目录
```

**重要提示**：当使用`decompose_prd`工具并采用`file://`格式指定PRD文件路径时，**必须**使用绝对路径。例如：
- Windows系统: `file:///C:/Users/username/documents/prd.md`
- Linux/macOS系统: `file:///home/username/projects/prd.md`

相对路径将无法被正确解析。

### 服务配置

```bash
export MCP_SERVICE_PORT=8000                    # 服务端口号
export MCP_LOG_LEVEL=INFO                       # 日志级别(DEBUG, INFO, WARNING, ERROR)
```

## 2. Cursor IDE配置

在Cursor中配置MCP服务的示例 (`~/.cursor/mcp.json`)：

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
        "D:\\code\\git_project\\task-manager-mcp\\src\\server.py" // 注意: 替换为你的 server.py 绝对路径
      ],
      "env": {
        "GEMINI_API_KEY": "<你的Gemini API Key>",
        "HTTP_PROXY": "http://127.0.0.1:7890", // 代理设置 (如果需要)
        "HTTPS_PROXY": "http://127.0.0.1:7890", // 代理设置 (如果需要)
        "MODEL_NAME": "gemini-1.5-flash", // 或 openai 模型
        "LLM_PROVIDER": "gemini", // 或 openai
        "MCP_OUTPUT_DIR": "D:\\path\\to\\your\\output\\dir\\" // 可选：指定输出目录
      }
    }
    // 可能有其他服务器配置...
  }
}
```

**注意:**
- 确保 `command` 和 `args` 正确指向你的 `uv` 命令和 `server.py` 的绝对路径。
- 对于Windows路径，需要使用双反斜杠（例如：`D:\\path\\to\\file.py`）。
- 正确配置 `env` 中的 API 密钥、代理（如果需要）、模型名称和输出目录。

## 3. Docker配置示例

### Dockerfile

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

### docker-compose.yml

```yaml
version: '3'

services:
  task-manager-mcp:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./output:/app/output
    environment:
      - GEMINI_API_KEY=your-api-key-here
      - MODEL_NAME=gemini-1.5-flash
      - LLM_PROVIDER=gemini
      - MCP_LOG_LEVEL=INFO
    restart: unless-stopped

  # 未来可能的数据库服务
  # postgres:
  #   image: postgres:14
  #   environment:
  #     - POSTGRES_USER=taskmanager
  #     - POSTGRES_PASSWORD=password
  #     - POSTGRES_DB=tasks
  #   volumes:
  #     - postgres_data:/var/lib/postgresql/data
  #   ports:
  #     - "5432:5432"

# volumes:
#   postgres_data:
```

## 4. Nginx 反向代理配置

当需要通过HTTPS提供服务或进行负载均衡时，可以使用Nginx作为反向代理：

```nginx
server {
    listen 443 ssl;
    server_name task-manager.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location /mcp {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## 5. 性能调优

### 使用uv运行服务

推荐使用uv运行服务，以获得更快的启动速度和更好的子解释器隔离：

```bash
# 基本运行
uv run --with fastmcp fastmcp run src/server.py

# 高级配置：启用JIT编译(仅PyPy)，调整线程池
UV_JIT=1 UV_THREAD_POOL_SIZE=8 uv run --with fastmcp fastmcp run src/server.py
```

### 内存优化技巧

- 如果使用内存存储模式（默认），定期导出任务数据：

```bash
# 设置自动导出间隔（秒）
export MCP_AUTO_EXPORT_INTERVAL=3600
```

- 限制大型PRD文档解析的任务数：

```bash
# 限制每次PRD解析生成的最大任务数
export MCP_MAX_TASKS_PER_PRD=100
```

### LLM优化

调整LLM调用的超时和重试参数：

```bash
# 设置LLM调用超时时间(秒)
export LLM_TIMEOUT=60

# 设置LLM调用最大重试次数
export LLM_MAX_RETRIES=3
``` 