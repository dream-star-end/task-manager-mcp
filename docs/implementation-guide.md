# 任务管理MCP服务实现指南

## 1. 项目结构

推荐的项目结构如下：

```
task-manager-mcp/
├── server.py                # 主程序入口
├── models/
│   └── task.py              # 任务数据模型
├── services/
│   ├── task_service.py      # 任务管理核心逻辑
│   └── prd_parser.py        # PRD解析服务
├── storage/
│   └── task_storage.py      # 任务存储实现
├── utils/
│   ├── id_generator.py      # ID生成器
│   └── dependency_checker.py # 依赖检查工具
└── docs/
    ├── design.md            # 设计文档
    ├── mcp-rules.md         # MCP调用规则
    └── getting-started.md   # 快速入门指南
```

## 2. 核心组件实现

### 2.1 服务器入口 (server.py)

```python
from fastmcp import FastMCP
from services.task_service import TaskService
import mcp.types as types
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastMCP 实例，提供服务名称
mcp = FastMCP("task-manager")
task_service = TaskService()

@mcp.tool("decompose_prd")
async def decompose_prd(prd_content: str):
    """解析PRD文档，自动拆解为任务列表"""
    logger.info(f"解析PRD文档: {prd_content[:50]}...")
    return await task_service.decompose_prd(prd_content)

@mcp.tool("add_task")
async def add_task(name: str, description: str = "", depends_on: list[str] = None, parent_task: str = None):
    """创建新任务"""
    logger.info(f"创建新任务: {name}")
    return task_service.add_task(name, description, depends_on, parent_task)

@mcp.tool("update_task")
async def update_task(task_id: str, name: str = None, description: str = None, status: str = None, code_files: list[str] = None):
    """更新现有任务信息"""
    logger.info(f"更新任务 {task_id}")
    return task_service.update_task(task_id, name, description, status, code_files)

@mcp.tool("set_task_dependency")
async def set_task_dependency(task_id: str, depends_on: list[str]):
    """设置任务依赖关系"""
    logger.info(f"设置任务 {task_id} 的依赖关系")
    return task_service.set_task_dependency(task_id, depends_on)

@mcp.tool("get_task_list")
async def get_task_list(status: str = None, parent_task: str = None):
    """获取任务列表"""
    logger.info(f"获取任务列表 (状态: {status}, 父任务: {parent_task})")
    return task_service.get_task_list(status, parent_task)

@mcp.tool("get_next_executable_task")
async def get_next_executable_task():
    """获取下一个可执行任务"""
    logger.info("获取下一个可执行任务")
    return task_service.get_next_executable_task()

# 可选: 添加一个工具用于列出所有可用工具及其说明
@mcp.tool("use_description")
async def list_tools():
    """列出所有可用的工具及其参数"""
    return {
        "tools": [
            {
                "name": "decompose_prd",
                "description": "解析PRD文档，自动拆解为任务列表",
                "parameters": {
                    "prd_content": {
                        "type": "string",
                        "description": "PRD文档内容或资源标识符",
                        "required": True
                    }
                }
            },
            # ... 其他工具的描述
        ]
    }

if __name__ == "__main__":
    import uvicorn
    # 从环境变量中获取端口，默认为8000
    port = int(os.environ.get("MCP_SERVICE_PORT", 8000))
    uvicorn.run("server:mcp", host="0.0.0.0", port=port, reload=True)
```

### 2.2 任务模型 (models/task.py)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid
import datetime

class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    BLOCKED = "blocked"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    depends_on: List[str] = Field(default_factory=list)
    subtasks: List[str] = Field(default_factory=list)
    parent_task: Optional[str] = None
    code_files: List[str] = Field(default_factory=list)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "depends_on": self.depends_on,
            "subtasks": self.subtasks,
            "parent_task": self.parent_task,
            "code_files": self.code_files,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
```

### 2.3 任务存储 (storage/task_storage.py)

```python
from models.task import Task, TaskStatus
from typing import List, Optional, Dict

class TaskStorage:
    """简单的内存存储实现，后期可替换为数据库存储"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        
    def add(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task
        
    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
        
    def update(self, task: Task) -> Task:
        task.updated_at = datetime.datetime.now()
        self.tasks[task.id] = task
        return task
        
    def list_all(self) -> List[Task]:
        return list(self.tasks.values())
        
    def list_by_status(self, status: TaskStatus) -> List[Task]:
        return [task for task in self.tasks.values() if task.status == status]
        
    def list_by_parent(self, parent_id: str) -> List[Task]:
        return [task for task in self.tasks.values() if task.parent_task == parent_id]
```

## 3. 核心服务实现

### 3.1 任务服务 (services/task_service.py)

关键功能实现代码示例：

```python
# 获取下一个可执行任务的实现
def get_next_executable_task(self):
    # 1. 首先查找状态为doing的任务
    doing_tasks = self.storage.list_by_status(TaskStatus.DOING)
    if doing_tasks:
        # 如果有正在进行的任务，优先返回第一个
        return doing_tasks[0].to_dict()
        
    # 2. 如果没有doing状态的任务，查找可执行的todo任务
    todo_tasks = self.storage.list_by_status(TaskStatus.TODO)
    executable_tasks = []
    
    for task in todo_tasks:
        # 检查依赖任务是否都已完成
        all_deps_done = True
        for dep_id in task.depends_on:
            dep_task = self.storage.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.DONE:
                all_deps_done = False
                break
                
        if all_deps_done:
            executable_tasks.append(task)
    
    if not executable_tasks:
        return None
        
    # 根据优先级或创建时间排序，这里简单地返回第一个
    # 实际实现可以添加更复杂的优先级逻辑
    return executable_tasks[0].to_dict()
```

### 3.2 PRD解析服务 (services/prd_parser.py)

```python
import re
from typing import List, Dict
from models.task import Task

class PrdParser:
    """PRD文档解析器"""
    
    async def parse(self, content: str) -> List[Task]:
        """
        解析PRD文档内容，提取任务和依赖关系
        
        这里只是一个简单的实现示例，实际应用中可能需要使用
        更复杂的NLP技术或与LLM集成来进行更智能的解析
        """
        tasks = []
        
        # 简单示例：提取标题作为任务
        # 实际实现可能更复杂，例如使用外部LLM服务
        headers = re.findall(r'##\s+(.*)', content)
        
        for i, header in enumerate(headers):
            task = Task(
                name=header,
                description=f"从PRD自动提取的任务: {header}"
            )
            tasks.append(task)
            
        # 简单的依赖关系：假设任务按顺序依赖
        for i in range(1, len(tasks)):
            tasks[i].depends_on.append(tasks[i-1].id)
            
        return tasks
```

## 4. 测试策略

### 4.1 单元测试

为核心功能编写单元测试，特别是：
- 任务依赖检查
- 任务状态转换
- get_next_executable_task 逻辑

```python
# tests/test_task_service.py 示例
def test_get_next_executable_task():
    storage = TaskStorage()
    service = TaskService(storage)
    
    # 添加测试任务
    task1 = Task(name="Task 1")
    task2 = Task(name="Task 2", depends_on=[task1.id])
    
    storage.add(task1)
    storage.add(task2)
    
    # 测试返回没有依赖的任务
    next_task = service.get_next_executable_task()
    assert next_task["id"] == task1.id
    
    # 将任务1标记为完成
    task1.status = TaskStatus.DONE
    storage.update(task1)
    
    # 测试返回依赖已满足的任务
    next_task = service.get_next_executable_task()
    assert next_task["id"] == task2.id
```

## 5. 部署指南

### 5.1 Docker部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.2 运行命令

```bash
# 构建镜像
docker build -t task-manager-mcp .

# 运行容器
docker run -d -p 8000:8000 --name task-manager task-manager-mcp
``` 