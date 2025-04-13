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

使用pip安装所需依赖：

```bash
# 安装MCP SDK
pip install mcp-python-sdk

# 安装其他依赖
pip install -r requirements.txt
```

`requirements.txt`文件内容示例：

```
uvicorn>=0.15.0
pydantic>=1.8.2
fastapi>=0.70.0
```

### 2.4 基本配置

创建配置文件：

```bash
# 复制示例配置文件
cp config.example.yaml config.yaml
```

编辑`config.yaml`，根据需要调整设置：

```yaml
# 服务设置
service:
  name: "task-manager-mcp"
  host: "0.0.0.0"
  port: 8000
  debug: false

# MCP服务配置
mcp:
  name: "task-manager"
  sse: true
  base_path: "/mcp"
```

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
pip install -r requirements-dev.txt
```

开发环境配置文件`config-dev.yaml`：

```yaml
service:
  debug: true

logging:
  level: "DEBUG"
```

### 3.2 生产环境

为生产环境进行额外设置：

```bash
# 安装生产依赖
pip install -r requirements-prod.txt

# 生成密钥
python -c "import secrets; print(secrets.token_hex(32))" > .secret_key
```

生产环境配置示例`config-prod.yaml`：

```yaml
service:
  debug: false

logging:
  level: "WARNING"
  file: "/var/log/task-manager.log"
```

## 4. 在Cursor IDE中配置

### 4.1 配置MCP服务

编辑Cursor的MCP配置文件：

* Windows: `C:\Users\<用户名>\.cursor\mcp.json`
* macOS: `~/.cursor/mcp.json`
* Linux: `~/.cursor/mcp.json`

添加以下配置：

```json
"task-manager": {
  "command": "/path/to/python",
  "args": [
    "-m",
    "mcp",
    "run",
    "/absolute/path/to/task-manager-mcp/server.py"
  ],
  "env": {
    "MCP_SERVICE_PORT": "8000",
    "MCP_CONFIG_PATH": "/absolute/path/to/task-manager-mcp/config.yaml"
  }
}
```

确保所有路径都使用绝对路径，Windows路径使用双反斜杠，例如：`C:\\Users\\name\\projects\\task-manager-mcp\\server.py`。

### 4.2 重启Cursor IDE

配置完成后，重启Cursor IDE以应用更改。

## 5. Docker安装

### 5.1 使用预构建镜像

```bash
# 拉取镜像
docker pull yourusername/task-manager-mcp:latest

# 运行容器
docker run -p 8000:8000 -v $(pwd)/config.yaml:/app/config.yaml yourusername/task-manager-mcp
```

### 5.2 本地构建

```bash
# 构建镜像
docker build -t task-manager-mcp .

# 运行容器
docker run -p 8000:8000 -v $(pwd)/config.yaml:/app/config.yaml task-manager-mcp
```

## 6. 验证安装

启动服务：

```bash
python -m mcp run server.py
```

测试服务是否正常运行：

```bash
# 使用curl请求
curl http://localhost:8000/mcp/status

# 预期输出
{"status":"ok","version":"1.0.0"}
```

或者在浏览器中访问：`http://localhost:8000/mcp`

## 7. 高级配置

### 7.1 环境变量

可以使用环境变量覆盖配置：

```bash
# 设置服务端口
export MCP_SERVICE_PORT=9000

# 设置日志级别
export MCP_LOG_LEVEL=DEBUG

# 使用自定义配置文件
export MCP_CONFIG_PATH=/path/to/custom-config.yaml

# DeepSeek API配置（用于PRD解析）
export DEEPSEEK_API_KEY=your_api_key_here
```

如果未设置DeepSeek API密钥，系统将退回到基本的PRD解析模式，只提取标题作为任务。

### 7.2 数据库配置

默认使用内存存储，可配置数据库（未来支持）：

```yaml
storage:
  type: "sqlite"
  database:
    url: "sqlite:///tasks.db"
```

## 8. 常见问题

### 8.1 依赖安装失败

问题：安装依赖时出现错误

解决：确保Python版本兼容，并尝试：

```bash
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

### 8.2 端口冲突

问题：启动服务时显示端口已被占用

解决：修改配置文件中的端口或使用环境变量：

```bash
export MCP_SERVICE_PORT=9000
```

### 8.3 Cursor无法连接

问题：Cursor IDE无法连接到MCP服务

解决：
1. 确认服务正在运行
2. 检查配置中的路径是否正确
3. 确保防火墙未阻止连接
4. 尝试使用`127.0.0.1`替代`localhost`

## 9. 更新

更新到最新版本：

```bash
# 更新代码库
git pull

# 更新依赖
pip install -r requirements.txt --upgrade
``` 