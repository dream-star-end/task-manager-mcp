# 任务管理MCP服务配置示例

本文档提供任务管理MCP服务的配置示例，包括服务配置和部署选项。

## 1. 配置文件示例

### config.yaml

```yaml
# 任务管理MCP服务配置

# 服务设置
service:
  name: "task-manager-mcp"
  host: "0.0.0.0"
  port: 8000
  debug: false

# MCP服务配置
mcp:
  # 服务名称（在IDE中引用）
  name: "task-manager"
  # 是否开启SSE模式
  sse: true
  # 基础URL路径，默认为/mcp
  base_path: "/mcp"
  # 配置工具ID前缀，可选
  tool_id_prefix: ""

# 存储设置
storage:
  # 目前支持 "memory"，后续将支持 "sqlite", "postgresql", "redis"
  type: "memory"
  # 数据库配置（当使用数据库存储时需要）
  # database:
  #   url: "sqlite:///tasks.db"
  #   pool_size: 10

# 任务设置
tasks:
  # 默认任务状态
  default_status: "todo"
  # 是否启用任务优先级
  use_priority: false
  # 是否启用任务截止日期
  use_deadline: false
  # 代码文件路径记录格式
  code_files_format: "[CODE_FILES: {files}]"

# 日志配置
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "task-manager.log"
```

## 2. 环境变量配置

可以使用环境变量覆盖配置文件中的设置：

```bash
# 服务设置
export MCP_SERVICE_PORT=9000
export MCP_SERVICE_DEBUG=true

# MCP设置
export MCP_NAME=task-manager
export MCP_BASE_PATH=/task-manager
export MCP_SSE=true

# 存储设置
export MCP_STORAGE_TYPE=sqlite
export MCP_DATABASE_URL=sqlite:///tasks.db

# 日志设置
export MCP_LOG_LEVEL=DEBUG
```

## 3. Cursor IDE配置

在Cursor中配置MCP服务的示例：

```json
// ~/.cursor/mcp.json
{
  "task-manager": {
    "command": "C:\\Python310\\python.exe",
    "args": [
      "-m",
      "mcp",
      "run",
      "D:\\projects\\task-manager-mcp\\server.py"
    ],
    "env": {
      "MCP_SERVICE_PORT": "8000",
      "MCP_LOG_LEVEL": "INFO"
    }
  }
}
```

## 4. Docker Compose 示例

### docker-compose.yml

```yaml
version: '3'

services:
  task-manager-mcp:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
    environment:
      - MCP_NAME=task-manager
      - MCP_LOG_LEVEL=INFO
    restart: unless-stopped

  # 数据库示例（后续扩展时使用）
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

## 5. Nginx 反向代理配置

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
        
        # WebSocket 支持 (SSE 连接)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## 6. 性能调优

对于高负载场景，可以考虑以下配置调整：

### uvicorn 运行参数

```bash
uvicorn server:mcp --host 0.0.0.0 --port 8000 --workers 4 --limit-concurrency 100 --timeout-keep-alive 120
```

参数说明：
- `--workers`: 工作进程数，通常设置为 CPU 核心数的 2 倍
- `--limit-concurrency`: 每个工作进程的最大并发连接数
- `--timeout-keep-alive`: 保持连接的超时时间（秒）

### 内存优化

对于内存存储模式，可以通过环境变量限制最大任务数量：

```bash
export MCP_MAX_TASKS=10000
``` 